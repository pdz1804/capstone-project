"""
Integration Examples for File Metadata System

This module demonstrates how to integrate the metadata service throughout
your RAG pipeline for comprehensive file tracking.
"""

import logging
from pathlib import Path
from app.services.file_metadata_service import FileMetadataService

logger = logging.getLogger(__name__)


# ============================================================================
# Example 1: Integration with Processing Pipeline
# ============================================================================

def process_document_with_metadata_tracking(file_path: str, user_id: str):
    """
    Example: Process a document and track metadata through each stage.
    
    This shows how to integrate metadata updates into your processing pipeline.
    """
    from src.processor.pipeline import process_document
    
    metadata_svc = FileMetadataService()
    
    try:
        # Mark processing as started
        metadata_svc.update_status(file_path, status="processing")
        
        # Stage 1: Normalize
        logger.info(f"Stage 1: Normalizing {Path(file_path).name}")
        process_document(file_path, stage="normalize")
        metadata_svc.mark_stage_complete(file_path, "normalize")
        
        # Stage 2: Extract Media
        logger.info(f"Stage 2: Extracting media from {Path(file_path).name}")
        process_document(file_path, stage="extract_media")
        metadata_svc.mark_stage_complete(file_path, "extract_media")
        
        # Stage 3: Docling (OCR, VLM, ASR)
        logger.info(f"Stage 3: Running Docling on {Path(file_path).name}")
        process_document(file_path, stage="docling")
        metadata_svc.mark_stage_complete(file_path, "docling")
        
        # Stage 4: Chunking
        logger.info(f"Stage 4: Chunking {Path(file_path).name}")
        process_document(file_path, stage="chunking")
        metadata_svc.mark_stage_complete(file_path, "chunking")
        
        # Stage 5: Indexing
        logger.info(f"Stage 5: Indexing {Path(file_path).name}")
        process_document(file_path, stage="indexing")
        metadata_svc.mark_stage_complete(file_path, "indexing")
        
        # Mark as complete
        metadata_svc.mark_complete(file_path)
        logger.info(f"Successfully processed {Path(file_path).name}")
        
    except Exception as e:
        logger.error(f"Error processing {Path(file_path).name}: {e}")
        metadata_svc.mark_failed(
            file_path,
            error_message=str(e),
            error_details=repr(e),
        )
        raise


# ============================================================================
# Example 2: Batch Processing with Statistics
# ============================================================================

def batch_process_with_stats(directory: str):
    """
    Example: Process multiple files and generate statistics.
    
    Shows how to:
    - Find pending files
    - Process them with tracking
    - Generate aggregate statistics
    """
    metadata_svc = FileMetadataService()
    dir_path = Path(directory)
    
    # Get all pending files
    pending_files = metadata_svc.list_file_metadata(dir_path, status_filter="pending")
    
    logger.info(f"Processing {len(pending_files)} pending files")
    
    processed_count = 0
    failed_count = 0
    
    for metadata in pending_files:
        try:
            logger.info(f"[{processed_count + failed_count + 1}/{len(pending_files)}] Processing: {metadata.original_filename}")
            process_document_with_metadata_tracking(metadata.file_path, metadata.user_id)
            processed_count += 1
        except Exception as e:
            logger.warning(f"Failed: {e}")
            failed_count += 1
    
    # Generate stats
    stats = metadata_svc.get_processing_stats(dir_path)
    
    summary = (
        f"BATCH PROCESSING SUMMARY - Processed: {processed_count}, Failed: {failed_count} | "
        f"Directory: Pending={stats['by_status']['pending']}, Processing={stats['by_status']['processing']}, "
        f"Completed={stats['by_status']['completed']}, Failed={stats['by_status']['failed']} | "
        f"Total size: {stats['total_size_bytes'] / (1024*1024):.2f} MB | "
        f"Avg time: {stats['average_processing_time_seconds']:.1f}s" if stats['average_processing_time_seconds'] else "N/A"
    )
    logger.info(summary)
    
    return stats


# ============================================================================
# Example 3: Frontend Dashboard Data Generation
# ============================================================================

def get_dashboard_data(user_id: str) -> dict:
    """
    Example: Generate data for a frontend dashboard.
    
    Returns structured data for displaying:
    - File upload status
    - Processing queue
    - Recently completed files
    - Failed files with errors
    """
    from app.core.paths import workspace_paths_for_user
    
    metadata_svc = FileMetadataService()
    paths = workspace_paths_for_user(user_id)
    
    # Get all metadata
    all_files = metadata_svc.list_file_metadata(paths.input_dir)
    
    # Organize by status
    dashboard = {
        "summary": {
            "total_files": len(all_files),
            "total_size_gb": sum(m.file_size for m in all_files) / (1024**3),
        },
        "by_status": {
            "pending": [],
            "processing": [],
            "completed": [],
            "failed": [],
        },
        "queue": [],
        "recent_failures": [],
    }
    
    for metadata in all_files:
        file_info = {
            "name": metadata.original_filename,
            "size_mb": metadata.file_size / (1024**2),
            "upload_time": metadata.upload_time,
            "status": metadata.status,
            "progress": len(metadata.completed_stages) / 6 * 100,  # 6 stages total
            "stages": metadata.completed_stages,
        }
        
        # Add to appropriate status bucket
        dashboard["by_status"][metadata.status].append(file_info)
        
        # Build processing queue (pending + processing)
        if metadata.status in ("pending", "processing"):
            dashboard["queue"].append(file_info)
        
        # Collect recent failures
        if metadata.status == "failed":
            dashboard["recent_failures"].append({
                **file_info,
                "error": metadata.error_message,
                "details": metadata.error_details,
            })
    
    # Sort queue by upload time (FIFO)
    dashboard["queue"].sort(key=lambda x: x["upload_time"])
    
    return dashboard


# ============================================================================
# Example 4: Error Recovery & Retry Logic
# ============================================================================

def retry_failed_files(directory: str, max_retries: int = 3):
    """
    Example: Retry processing failed files.
    
    Shows how to:
    - Find files that failed
    - Attempt reprocessing
    - Track retry attempts (in metadata)
    """
    metadata_svc = FileMetadataService()
    dir_path = Path(directory)
    
    # Get all failed files
    failed_files = metadata_svc.list_file_metadata(dir_path, status_filter="failed")
    
    logger.info(f"Retrying {len(failed_files)} failed files (max {max_retries} attempts)")
    
    recovered = 0
    still_failed = 0
    
    for metadata in failed_files:
        logger.info(f"Retrying: {metadata.original_filename} (previous error: {metadata.error_message})")
        
        for attempt in range(1, max_retries + 1):
            try:
                logger.debug(f"Attempt {attempt}/{max_retries}")
                process_document_with_metadata_tracking(
                    metadata.file_path,
                    metadata.user_id
                )
                logger.info(f"File recovered successfully")
                recovered += 1
                break
            except Exception as e:
                logger.warning(f"Attempt {attempt} failed: {e}")
                if attempt == max_retries:
                    logger.error(f"Max retries exceeded for {metadata.original_filename}")
                    still_failed += 1
    
    print(f"\nRetry Summary: {recovered} recovered, {still_failed} still failing\n")
    return recovered, still_failed


# ============================================================================
# Example 5: Monitoring & Health Checks
# ============================================================================

def health_check(directory: str) -> bool:
    """
    Example: Perform health checks on file processing.
    
    Returns True if all is well, False if issues detected.
    """
    metadata_svc = FileMetadataService()
    dir_path = Path(directory)
    
    stats = metadata_svc.get_processing_stats(dir_path)
    
    issues = []
    
    # Check for too many failed files
    if stats['by_status']['failed'] > stats['total_files'] * 0.1:  # 10% failure rate
        issues.append(f"High failure rate: {stats['by_status']['failed']} failed files")
    
    # Check for stuck processing files
    processing = metadata_svc.list_file_metadata(dir_path, status_filter="processing")
    from datetime import datetime, timezone, timedelta
    now = datetime.now(timezone.utc)
    stuck_threshold = timedelta(hours=2)
    
    for metadata in processing:
        if metadata.processing_start_time:
            start = datetime.fromisoformat(metadata.processing_start_time)
            if now - start > stuck_threshold:
                issues.append(f"Stuck file: {metadata.original_filename} (processing for {(now - start).total_seconds() / 3600:.1f}h)")
    
    # Check storage capacity
    total_size = stats['total_size_bytes'] / (1024**3)  # Convert to GB
    if total_size > 100:  # 100GB threshold
        issues.append(f"High storage usage: {total_size:.1f} GB")
    
    if issues:
        logger.warning(f"Health Check Issues: {'; '.join(issues)}")
        return False
    else:
        logger.info("All health checks passed")
        return True


# ============================================================================
# Example 6: Export Metadata for Reporting
# ============================================================================

def export_metadata_report(directory: str, output_file: str):
    """
    Example: Export metadata to CSV for reporting.
    
    Shows how to generate reports for stakeholders.
    """
    import csv
    
    metadata_svc = FileMetadataService()
    dir_path = Path(directory)
    
    all_files = metadata_svc.list_file_metadata(dir_path)
    
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'filename',
            'status',
            'size_mb',
            'upload_time',
            'processing_duration_seconds',
            'completed_stages',
            'error_message',
        ])
        writer.writeheader()
        
        for metadata in all_files:
            duration = metadata_svc._calculate_duration(
                metadata.processing_start_time,
                metadata.processing_end_time,
            )
            
            writer.writerow({
                'filename': metadata.original_filename,
                'status': metadata.status,
                'size_mb': f"{metadata.file_size / (1024**2):.2f}",
                'upload_time': metadata.upload_time,
                'processing_duration_seconds': duration or 'N/A',
                'completed_stages': ';'.join(metadata.completed_stages),
                'error_message': metadata.error_message or '',
            })
    
    logger.info(f"Report exported to {output_file}")


# ============================================================================
# Usage Examples
# ============================================================================

if __name__ == "__main__":
    # Example 1: Process single document with tracking
    # process_document_with_metadata_tracking("/path/to/file.pdf", "user_123")
    
    # Example 2: Batch process with statistics
    # batch_process_with_stats("/data/workspace/input")
    
    # Example 3: Get dashboard data
    # dashboard = get_dashboard_data("user_123")
    # print(dashboard)
    
    # Example 4: Retry failed files
    # recovered, still_failing = retry_failed_files("/data/workspace/input")
    
    # Example 5: Health checks
    # is_healthy = health_check("/data/workspace/input")
    
    # Example 6: Export report
    # export_metadata_report("/data/workspace/input", "metadata_report.csv")
    
    logger.info("Metadata integration examples loaded")
