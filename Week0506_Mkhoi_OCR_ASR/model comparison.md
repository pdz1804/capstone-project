# **ASR Model Benchmark Comparison**

| Model / API                               | Word Error Rate (WER) (%) | Processing time (full 15 min 31 s video) | Time / min audio | Real-Time Factor (RTF) | Limit on Audio Length | Relative Cost      | Strengths                                                   | Weaknesses                                  | Vietnamese Support                 | Recommended Use Case                                                | Source / Benchmark                           |
| :---------------------------------------- | :------------------------ | :--------------------------------------- | :--------------- | ---------------------- | :-------------------- | :----------------- | :---------------------------------------------------------- | :------------------------------------------ | :--------------------------------- | :------------------------------------------------------------------ | :------------------------------------------- |
| **Whisper (Large-v3, local)**       | ≈ 10.0 %                 | 502 s                                    | 32.4 s / min    | 0.54                   | Unlimited             | Free (open source) | Extremely robust, multilingual, accurate on noisy speech    | Slow on CPU; large model (\~1.5 GB weights) | Good (multilingual)                | Offline transcription, research experiments, multilingual datasets  | OpenAI Whisper paper (2022); WithAqua (2024) |
| **Gemini 2.5 Flash**                | ≈ 5.5 %                  | 19 s                                     | 1.23 s / min     | 0.02                   | ≤ 60 min             | Paid API           | Fast multimodal processing (audio\+ video \+ text \+ image) | Length limit to 60 min; black-box model     | Excellent                          | Fast multimodal analytics, enterprise API workflows                 | Google Research (2024)                       |
| **wav2vec 2.0 (Large / XLS-R)**     | ≈ 4.8 %                  | 279 s                                    | 17.99 s / min    | 0.3                    | Unlimited             | Free (open source) | Best open-source WER for English; low noise impact          | Needs fine-tuning for non-English           | Partial (Vietnamese via XLS-R 53\) | Academic research, fine-tuning for Vietnamese corpora               | Meta AI XLS-R benchmarks (2021)              |
| **Parakeet-TDT 0.6B (NVIDIA NeMo)** | ≈ 6.0 %                  | 9 s                                      | 0.58 s / min     | 0.009                  | Unlimited             | Free (open source) | Very fast and lightweight                                   | Limited language support (English only)     | No (English only weights)          | On-device or edge deployment for English speechNVIDIA Parakeet docs | NVIDIA Parakeet Docs (2024)                 |

# **OCR Model Benchmark Comparison**

| Model / API                       | Character Error Rate (CER) (%) | Processing Time (15-page, text-heavy) | Time / page   | Relative Speed (↓ = faster) | Limit on Page Count | Relative Cost | Strengths                                                     | Weaknesses                          | Vietnamese Support            | Recommended Use Case                                          | Source / Benchmark                       |
| :-------------------------------- | :----------------------------- | :------------------------------------ | :------------ | :--------------------------- | :------------------ | :------------ | :------------------------------------------------------------ | :---------------------------------- | :---------------------------- | :------------------------------------------------------------ | :--------------------------------------- |
| **Tesseract 5**             | ≈ 2.8 %                       | 42 s                                  | 2.8 s / page  | 1.0 × (base)                | Unlimited           | Free          | Mature, multilingual (100+ langs), customizable               | Sensitive to low-quality scans      | Good                          | Offline OCR, research, small-scale document parsing           | Google / UB Mannheim OCR Bench (2024)    |
| **PaddleOCR**               | ≈ 1.6 %                       | 24 s                                  | 1.6 s / page  | 0.6 ×                       | Unlimited           | Free          | Excellent multilingual + layout detection                     | Slightly harder to deploy           | Excellent                     | Fast multilingual OCR pipelines, academic + industry research | Baidu PaddleOCR Benchmarks (2024)        |
| **TrOCR**                   | ≈ 1.2 %                       | 54 s                                  | 3.6 s / page  | 1.3 ×                       | Unlimited           | Free          | Transformer-based, high accuracy on printed text              | Requires GPU; weaker on handwriting | Moderate (fine-tuning needed) | High-accuracy printed OCR, model fine-tuning for specific use | Microsoft TrOCR paper (2023)             |
| **Google Gemini 2.5 Flash** | ≈ 0.9 %                       | 8 s                                   | 0.53 s / page | 0.19 ×                      | ≤ 200 pages / call | Paid API      | Extremely fast; layout, handwriting, and multilingual support | Paid; black-box model               | Excellent                     | Enterprise document digitization, multimodal data extraction  | Google Cloud Vision / Gemini Docs (2024) |

# **Structured-Document Model Benchmark Comparison**

| Model / API                                          | Structural Error Rate (SER) (%) | Avg. F1 (Form Fields) | Processing Time (10-page mixed layout) | Time / page | Relative Speed (↓ = faster) | Input Limit  | Relative Cost | Strengths                                                                         | Weaknesses                                         | Vietnamese Support              | Recommended Use Case                                             | Source / Benchmark                          |
| :--------------------------------------------------- | :------------------------------- | :-------------------- | :------------------------------------- | :---------- | :--------------------------- | :----------- | :------------ | :-------------------------------------------------------------------------------- | :------------------------------------------------- | :------------------------------ | :--------------------------------------------------------------- | :------------------------------------------ |
| **Gemini 2.5 Flash**                           | ≈ 4.5 %                         | 0.97                  | 9 s                                    | 0.9 s/page  | 0.18×                       | ≤ 200 pages | Paid API      | Unified multimodal reasoning across image + text + layout + table OCR             | Paid; black-box; API call limits                   | Excellent                       | End-to-end document intelligence, invoices, contracts, and forms | Google Gemini Docs & Vision AI (2024–2025) |
| **LayoutLMv3**                                 | ≈ 6.2 %                         | 0.94                  | 45 s                                   | 4.5 s/page  | 1.0×                        | Unlimited    | Free (open)   | Strong at understanding form fields and visual-text alignment                     | Requires OCR preprocessing; large memory footprint | Moderate (via finetune)         | Research, structured document QA, key-value extraction           | Microsoft Research LayoutLMv3 (2022)        |
| **Donut (Document Understanding Transformer)** | ≈ 5.0 %                         | 0.95                  | 28 s                                   | 2.8 s/page  | 0.62×                       | Unlimited    | Free (open)   | End-to-end OCR-free transformer; handles receipts, invoices, handwriting          | Needs fine-tuning for domain & language            | Good (multilingual fine-tuning) | OCR-free document parsing, receipts, form digitization           | NAVER Clova AI Donut paper (2023)           |
| **Pix2Struct**                                 | ≈ 4.8 %                         | 0.96                  | 32 s                                   | 3.2 s/page  | 0.71×                       | Unlimited    | Free (open)   | Converts document images directly into structured text via vision encoder-decoder | Limited fine-tuned models; slower decoding         | Good (multilingual)             | Layout-aware captioning, document QA, screen parsing             | Google Research Pix2Struct (2023)           |

# **Trade-off Summary**

| Model / API                   | Speed (↓= faster) | Accuracy (↓\= better) | Vietnamese Support  | Cost     | Recommended Use Case                               | Trade-off Summary                                                    |
| :---------------------------- | :------------------ | :---------------------- | :------------------ | :------- | :------------------------------------------------- | :------------------------------------------------------------------- |
| **Gemini 2.5 Flash**    | 0.02                | 5.5 %                   | Excellent           | Paid API | Fast multimodal analytics, enterprise applications | Fastest and accurate; limited to 60 min inputs and API cost          |
| **Whisper Large-v3**    | 0.54                | 10 %                    | Good (multilingual) | Free     | Offline transcription, multilingual datasets       | Best balance of cost, quality, and Vietnamese support; slower on CPU |
| **wav2vec 2.0 (XLS-R)** | 0.3                 | 4.8 %                   | Partial             | Free     | Academic research, retraining                      | Strong base model; requires Vietnamese data and tuning               |
| **Parakeet-TDT 0.6B**   | 0.009               | 6 %                     | None                | Free     | Edge / on-device English ASR                       | Extremely fast but English-only                                      |

| Model / API                | Speed (↓= faster) | Accuracy (↓= better) | Vietnamese Support | Cost     | Recommended Use Case                         | Trade-off Summary                                                   |
| :------------------------- | :----------------- | :-------------------- | :----------------- | :------- | :------------------------------------------- | :------------------------------------------------------------------ |
| **Gemini 2.5 Flash** | 0.19 ×            | 0.9 %                 | Excellent          | Paid API | Enterprise-scale OCR & multimodal extraction | Fastest and most accurate; API cost and call limits apply           |
| **PaddleOCR v2.7**   | 0.6 ×             | 1.6 %                 | Excellent          | Free     | Open-source multilingual OCR pipelines       | Top open-source option; slightly complex setup                      |
| **Tesseract 5**      | 1.0 ×             | 2.8 %                 | Good               | Free     | Lightweight offline OCR for scanned PDFs     | Simple setup; accuracy lower on messy layouts                       |
| **TrOCR**            | 1.3 ×             | 1.2 %                 | Moderate           | Free     | High-quality printed-text OCR research       | Very accurate but slower; fine-tuning improves multilingual support |

| Model / API                | Speed (↓= faster) | Accuracy (↓= better) | Vietnamese Support | Cost     | Recommended Use Case                  | Trade-off Summary                                                 |
| :------------------------- | :----------------- | :-------------------- | :----------------- | :------- | :------------------------------------ | :---------------------------------------------------------------- |
| **Gemini 2.5 Flash** | 0.18×             | 4.5 %                 | Excellent          | Paid API | Complex multimodal document workflows | Fastest + most accurate; premium API cost and limited free access |
| **Pix2Struct**       | 0.71×             | 4.8 %                 | Good               | Free     | Research on visual-text understanding | Accurate but slower; good for structured visual QA tasks          |
| **Donut**            | 0.62×             | 5.0 %                 | Good               | Free     | Receipts, invoices, OCR-free tasks    | OCR-free and versatile; fine-tuning improves domain accuracy      |
| **LayoutLMv3**       | 1.0×              | 6.2 %                 | Moderate           | Free     | Key-value extraction, research        | Strong model but requires external OCR and preprocessing          |

Sources:

[https://voicewriter.io/speech-recognition-leaderboard](https://voicewriter.io/speech-recognition-leaderboard)

[https://idp-leaderboard.org](https://idp-leaderboard.org)

[https://huggingface.co/efficient-speech/lite-whisper-large-v3-turbo](https://huggingface.co/efficient-speech/lite-whisper-large-v3-turbo)

[https://arxiv.org/pdf/2111.09296](https://arxiv.org/pdf/2111.09296)

[https://developer.nvidia.com/blog/nvidia-speech-ai-models-deliver-industry-leading-accuracy-and-performance](https://developer.nvidia.com/blog/nvidia-speech-ai-models-deliver-industry-leading-accuracy-and-performance)

[https://arxiv.org/html/2506.05061v1](https://arxiv.org/html/2506.05061v1)

[https://github.com/microsoft/unilm/tree/master/trocr]()

[https://arxiv.org/pdf/2406.02555](https://arxiv.org/pdf/2406.02555)
