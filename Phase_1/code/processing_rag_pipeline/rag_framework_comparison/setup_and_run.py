"""
Quick setup and run script for RAG comparison
"""
import os
import sys
import subprocess
from pathlib import Path

def check_python_version():
    """Check if Python version is compatible"""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ is required")
        return False
    print(f"✅ Python {sys.version.split()[0]} detected")
    return True

def install_dependencies():
    """Install required dependencies"""
    print("📦 Installing dependencies...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to install dependencies")
        return False

def setup_environment():
    """Setup environment file"""
    env_example = Path(".env.example")
    env_file = Path(".env")
    
    if not env_file.exists() and env_example.exists():
        # Copy example file
        with open(env_example, 'r') as f:
            content = f.read()
        with open(env_file, 'w') as f:
            f.write(content)
        print("📝 Created .env file from template")
        print("⚠️  Please edit .env file with your API keys before running benchmarks")
        return False
    elif env_file.exists():
        print("✅ Environment file already exists")
        return True
    else:
        print("❌ No environment template found")
        return False

def create_directories():
    """Create necessary directories"""
    directories = ["data", "logs", "results"]
    for dir_name in directories:
        Path(dir_name).mkdir(exist_ok=True)
    print("✅ Created necessary directories")

def run_sample_benchmark():
    """Run a simple benchmark with manual RAG"""
    print("🚀 Running sample benchmark with Manual RAG...")
    try:
        # Change to src directory
        os.chdir("src")
        
        # Run manual RAG with sample data
        result = subprocess.run([
            sys.executable, "manual_rag/rag_system.py",
            "--vector-store", "faiss",
            "--llm", "openai",
            "--rebuild"
        ], capture_output=True, text=True, timeout=300)
        
        if result.returncode == 0:
            print("✅ Sample benchmark completed successfully")
            print("📊 Check the results/ directory for output files")
        else:
            print("❌ Sample benchmark failed")
            print(f"Error: {result.stderr}")
        
        # Return to original directory
        os.chdir("..")
        
    except subprocess.TimeoutExpired:
        print("⏱️ Benchmark timed out (5 minutes)")
    except Exception as e:
        print(f"❌ Error running benchmark: {e}")

def main():
    """Main setup and run function"""
    print("🔧 RAG Pipeline Comparison Setup")
    print("=" * 40)
    
    # Check Python version
    if not check_python_version():
        return
    
    # Install dependencies
    if not install_dependencies():
        return
    
    # Setup environment
    env_ready = setup_environment()
    
    # Create directories
    create_directories()
    
    print("\n🎯 Setup Complete!")
    
    if env_ready:
        print("\n🔍 Available commands:")
        print("1. Run individual implementations:")
        print("   cd src && python manual_rag/rag_system.py --rebuild")
        print("   cd src && python langchain_rag/rag_system.py --rebuild")
        print("   cd src && python llamaindex_rag/rag_system.py --rebuild")
        print("\n2. Run comprehensive benchmark:")
        print("   cd src && python benchmark_runner.py --rebuild")
        print("\n3. Generate report only:")
        print("   cd src && python benchmark_runner.py --report-only")
        
        # Ask if user wants to run sample
        try:
            response = input("\n🤔 Run sample benchmark with Manual RAG? (y/n): ").lower().strip()
            if response in ['y', 'yes']:
                run_sample_benchmark()
        except KeyboardInterrupt:
            print("\n👋 Setup completed. You can run benchmarks manually.")
    else:
        print("\n⚠️  Please configure your API keys in .env before running benchmarks")

if __name__ == "__main__":
    main()