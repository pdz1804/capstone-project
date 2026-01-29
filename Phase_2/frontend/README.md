# RAG Pipeline - Frontend

A modern, responsive web interface for the Multimodal RAG Pipeline. Built with React, Vite, and Tailwind CSS.

---

## 🎯 Overview

**Tech Stack:**
- ⚛️ **React 18** - Modern UI library
- ⚡ **Vite** - Fast development server and build tool
- 🎨 **Tailwind CSS** - Utility-first CSS framework
- 📡 **Axios** - HTTP client for API communication
- 🎭 **Lucide React** - Beautiful icon library
- 📝 **React Markdown** - Markdown rendering with math support (KaTeX)

**Features:**
- Drag-and-drop file upload
- Real-time file management
- Document processing pipeline control
- Index building and management
- Natural language search with multimodal results
- Text chunk results with scores and metadata
- Image page results from ColQwen vision-language model
- LLM-generated answers with citations
- Responsive design for all screen sizes

---

## 🚀 Quick Start

### 1. **Install Dependencies**

```bash
# Navigate to frontend directory
cd Phase_2/frontend

# Install Node.js dependencies
npm install
```

### 2. **Configure Environment (Optional)**

```bash
# Copy example environment file (if needed)
cp .env.example .env

# The frontend expects the backend API to run at:
# http://localhost:8000 (default)
# No configuration needed if using default backend port
```

### 3. **Run Development Server**

```bash
# Start the Vite dev server
npm run dev

# Frontend will start at http://localhost:5173
# The terminal will show the exact URL
```

### 4. **Open in Browser**

Navigate to: **http://localhost:5173**

---

## 🛠️ Available Scripts

```bash
# Development server with hot reload
npm run dev

# Build for production
npm run build

# Preview production build locally
npm run preview
```

---

## 🌐 Architecture

```
Frontend (React)          Backend (FastAPI)
┌─────────────────┐      ┌─────────────────┐
│                 │      │                 │
│  File Upload    │─────▶│  /api/upload    │
│  Component      │      │                 │
│                 │      │  Processing     │
│  Processing     │─────▶│  Pipeline       │
│  Control        │      │                 │
│                 │      │  Retrieval      │
│  Search/Query   │─────▶│  System         │
│  Interface      │      │                 │
│                 │◀─────│  Results +      │
│  Results        │      │  Generation     │
│  Display        │      │                 │
└─────────────────┘      └─────────────────┘
 localhost:5173           localhost:8000
```

---

## ✨ Features

### 📤 **File Upload**
- Drag-and-drop or click to select files
- Supports multiple file formats: PDF, DOCX, PPTX, TXT, MD, images, videos, audio
- Real-time upload progress
- View list of uploaded files

### 📁 **File Management**

- View all uploaded files with metadata
- Preview processed documents
- Delete unwanted files
- Download files
- Track processing stages (normalized, processed, indexed)

### ⚙️ **Processing Pipeline**

- One-click document processing
- Real-time processing status
- Progress tracking
- Error handling and reporting
- Support for multimodal documents (text, images, video, audio)

### 🔍 **Indexing**

- Build text indexes (BM25, Dense, Hybrid)
- Build image indexes (ColQwen vision-language model)
- View indexing statistics:
  - Number of indexed documents
  - Number of text chunks
  - Number of image pages
  - Active retrieval methods

### 🔎 **Search & Query**

- Natural language query input
- Multimodal retrieval:
  - **Text Results**: Ranked chunks with BM25 and Dense scores
  - **Image Results**: Visual document pages from ColQwen
- Result details:
  - Relevance scores
  - Source document metadata
  - Text snippets with highlighting
  - Page previews for images
- Expandable result cards for detailed view

### 🤖 **Answer Generation**

- LLM-powered answer generation (GPT-4o-mini default)
- Context-aware responses using retrieved chunks
- Citations and source references
- Support for multimodal context (text + images)
- Markdown rendering with math support (KaTeX)

---

## 📋 Prerequisites

### **Required**

- Node.js 16+ and npm
- Backend API running at http://localhost:8000

### **Backend Setup (if not already running)**

```bash
# In a separate terminal, navigate to backend
cd ../backend

# Install Python dependencies
pip install -r requirements.txt

# Set up environment
cp .env.example .env
# Edit .env: OPENAI_API_KEY="your-key-here"

# Run backend server
cd api
python main.py
```

---

## 🔧 Configuration

### **Backend API URL**

The frontend is configured to connect to `http://localhost:8000` by default.

To change this, update the `axios` baseURL in your API service file or use environment variables.

### **Environment Variables**

Create a `.env` file in the frontend directory (optional):

```env
VITE_API_URL=http://localhost:8000
```

Then update your axios configuration to use:
```javascript
const API_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';
```

---

## 📦 Dependencies

### **Core**
- `react` - UI library
- `react-dom` - React DOM rendering
- `vite` - Build tool and dev server
- `axios` - HTTP client

### **UI Components**
- `lucide-react` - Icon library
- `tailwindcss` - CSS framework
- `autoprefixer` - PostCSS plugin
- `postcss` - CSS processor

### **Markdown & Rendering**
- `react-markdown` - Markdown component
- `remark-gfm` - GitHub Flavored Markdown
- `remark-math` - Math support for markdown
- `rehype-katex` - KaTeX rendering for math
- `rehype-raw` - HTML in markdown

---

## 🎨 UI Components

### **Main Layout**
- Header with title and status
- Sidebar for navigation (Upload, Processed, Indexed)
- Main content area for search and results
- Responsive grid layout

### **Upload Section**
- Drag-and-drop zone
- File picker button
- Upload progress indicator
- File list with delete options

### **Processed Files View**
- Card-based file display
- File metadata (name, size, type)
- Processing stage indicators
- Quick actions (preview, delete)

### **Search Interface**
- Clean search input with submit button
- Loading states during search
- Results organized by type (text/image)
- Score-based ranking display

### **Results Display**
- Text chunks with relevance scores
- Image pages with thumbnails
- Expandable cards for details
- Source document information
- Generated answer section with markdown support

---

## 🚀 Development

### **Project Structure**

```
frontend/
├── index.html              # Entry HTML
├── package.json            # Dependencies
├── vite.config.js          # Vite configuration
├── tailwind.config.js      # Tailwind configuration
├── postcss.config.js       # PostCSS configuration
└── src/
    ├── main.jsx            # React entry point
    ├── App.jsx             # Main application component
    └── index.css           # Global styles (Tailwind imports)
```

### **Development Tips**

1. **Hot Module Replacement (HMR)**: Vite provides instant updates during development
2. **Tailwind Classes**: Use Tailwind utility classes for styling
3. **API Communication**: All API calls go through axios to http://localhost:8000
4. **State Management**: Currently uses React useState (can be upgraded to Redux/Zustand if needed)

### **Adding New Features**

1. **New API Endpoint**: Add axios call in `App.jsx` or create a separate API service file
2. **New UI Component**: Create component in `src/components/` (create this folder if needed)
3. **New Page**: Add routing with React Router (needs to be installed)

---

## 🏗️ Build for Production

```bash
# Build optimized production bundle
npm run build

# Preview production build
npm run preview
```

**Output**: Production files will be in `dist/` directory

**Deployment Options**:
- Static hosting: Vercel, Netlify, GitHub Pages
- CDN: CloudFlare, AWS S3 + CloudFront
- Docker: Create Dockerfile with nginx to serve static files

**Example Nginx Configuration**:
```nginx
server {
    listen 80;
    server_name yourdomain.com;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_cache_bypass $http_upgrade;
    }
}
```

---

## 🐛 Troubleshooting

### **Backend Connection Error**

**Problem**: "Network Error" or "ERR_CONNECTION_REFUSED"

**Solution**:
1. Verify backend is running at http://localhost:8000
2. Check backend logs for errors
3. Ensure CORS is enabled in backend (already configured in FastAPI)

### **Blank Page After Build**

**Problem**: Production build shows blank page

**Solution**:
1. Check browser console for errors
2. Ensure all assets are loaded correctly (check paths)
3. Verify environment variables are set correctly

### **Styling Issues**

**Problem**: Tailwind classes not working

**Solution**:
1. Run `npm install` to ensure all dependencies are installed
2. Check `tailwind.config.js` content paths
3. Verify PostCSS configuration

### **File Upload Not Working**

**Problem**: Files not uploading to backend

**Solution**:
1. Check file size limits (backend may have restrictions)
2. Verify file types are supported
3. Check network tab in browser DevTools for error responses

---

## 📚 Additional Resources

- [React Documentation](https://react.dev/)
- [Vite Documentation](https://vitejs.dev/)
- [Tailwind CSS Documentation](https://tailwindcss.com/)
- [Axios Documentation](https://axios-http.com/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## 🤝 Contributing

This is part of the Capstone Project - HCMUT CS251. For collaboration:

1. Follow React best practices
2. Use functional components with hooks
3. Maintain Tailwind utility-first approach
4. Test all features before committing
5. Update this README for new features

---

## 📄 License

MIT License - See [LICENSE](../LICENSE) file for details

---

**Last Updated**: January 29, 2026  
**Version**: 1.0.0  
**Team**: MKhoi (ASR/OCR), NKhoi (Retrieval/Embeddings), QPhu (Pipeline/Integration)
