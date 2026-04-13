import { useEffect, useState } from 'react';
import {
  ArrowRight,
  BookOpen,
  BrainCircuit,
  CheckCircle2,
  ChevronsDown,
  Clock3,
  Database,
  GraduationCap,
  LayoutPanelTop,
  Loader2,
  LogIn,
  Quote,
  Sparkles,
  Star,
  UserPlus,
  Zap,
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { authService } from '../services/auth_service';
import AppFooter from '../components/AppFooter';

const robotHeroSrc = '/hero-robot-800.jpg';
const robotHeroSrcSet = '/hero-robot-480.jpg 480w, /hero-robot-800.jpg 800w';

type AuthMode = 'login' | 'register';

const landingLinks = [
  { id: 'hero', label: 'Home' },
  { id: 'features', label: 'Features' },
  { id: 'workflow', label: 'Workflow' },
  { id: 'testimonials', label: 'Testimonials' },
  { id: 'auth', label: 'Get Started' },
] as const;

const valueHighlights = [
  {
    icon: Database,
    title: 'Multimodal knowledge ingestion',
    description: 'Support for video, audio, slides, documents, and images with lecture-aware processing.',
  },
  {
    icon: BrainCircuit,
    title: 'Semantic and visual retrieval',
    description: 'Combine BM25, dense, hybrid, and visual retrieval to improve academic query accuracy.',
  },
  {
    icon: LayoutPanelTop,
    title: 'Focused learning workspace',
    description: 'A clear interface for students and lecturers: content management, assistant chat, quizzes, and learning paths.',
  },
];

const processSteps = [
  {
    title: '1. Upload and process',
    detail: 'Normalize learning materials, run OCR/ASR, and produce structured lecture data.',
  },
  {
    title: '2. Build smart indexes',
    detail: 'Create text and image indexes that support multi-strategy retrieval for each learning goal.',
  },
  {
    title: '3. Ask with citations',
    detail: 'Generate grounded answers with explicit citations for quick verification.',
  },
  {
    title: '4. Track progress',
    detail: 'Monitor strengths and weaknesses, with personalized review recommendations.',
  },
];

const testimonials = [
  {
    quote:
      'I can revisit key ideas from lecture videos much faster. Citations make revision far more trustworthy.',
    name: 'Nguyễn Minh Khôi',
    role: 'Computer Science Student',
  },
  {
    quote:
      'BK-MInD helps me summarize lecture content by slide and timeline with excellent clarity.',
    name: 'Nguyễn Ngọc Khôi',
    role: 'University Lecturer',
  },
  {
    quote:
      'The quiz and learning path features are extremely useful for tracking weekly progress.',
    name: 'Nguyễn Quang Phú',
    role: 'AI Education Researcher',
  },
];

const impactStats = [
  { value: '37+', label: 'Standardized system requirements covered' },
  { value: '< 1s', label: 'Target text retrieval latency' },
  { value: '10K+', label: 'Document scalability goal' },
];

export default function LoginView() {
  const [authMode, setAuthMode] = useState<AuthMode>('login');
  const [activeSection, setActiveSection] = useState<string>('hero');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');

  useEffect(() => {
    const sections = document.querySelectorAll<HTMLElement>('[data-landing-section]');
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            setActiveSection(entry.target.id);
          }
        });
      },
      { threshold: 0.45 }
    );

    sections.forEach((section) => observer.observe(section));

    return () => observer.disconnect();
  }, []);

  const scrollToSection = (id: string) => {
    const el = document.getElementById(id);
    if (el) {
      el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  };

  const jumpToAuth = (mode: AuthMode) => {
    setAuthMode(mode);
    scrollToSection('auth');
  };

  const handleGoogleSignIn = async () => {
    setIsLoading(true);
    setError(null);
    try {
      await authService.login();
    } catch (err: any) {
      setError(err.message || 'Unable to sign in with Google. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleLocalRegister = async () => {
    setIsLoading(true);
    setError(null);
    try {
      await authService.registerWithAppAccount(email.trim(), password, displayName.trim() || undefined);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Registration failed');
    } finally {
      setIsLoading(false);
    }
  };

  const handleLocalLogin = async () => {
    setIsLoading(true);
    setError(null);
    try {
      await authService.loginWithAppAccount(email.trim(), password);
    } catch (err: any) {
      setError(err?.response?.data?.detail || err.message || 'Sign-in failed');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-sky-50 text-slate-900 flex flex-col relative overflow-x-clip">
      <div className="pointer-events-none absolute inset-0 -z-10 bg-[radial-gradient(circle_at_88%_16%,rgba(14,165,233,0.12),transparent_40%),radial-gradient(circle_at_8%_0%,rgba(56,189,248,0.14),transparent_36%)]" />

      <header className="sticky top-0 z-40 border-b border-sky-100/90 bg-white/90 backdrop-blur-md">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 h-18 py-3 flex items-center justify-between gap-4">
          <button
            type="button"
            onClick={() => scrollToSection('hero')}
            className="inline-flex items-center gap-3 cursor-pointer"
          >
            <span className="w-10 h-10 rounded-xl bg-sky-600 text-white flex items-center justify-center shadow-sm">
              <BookOpen className="w-5 h-5" />
            </span>
            <span className="text-left">
              <span className="block text-base font-bold [font-family:var(--font-display)] tracking-tight">BK-MInD</span>
              <span className="block text-xs text-slate-500">AI for students and lecturers</span>
            </span>
          </button>

          <nav className="hidden lg:flex items-center gap-1 rounded-full border border-sky-100 bg-white p-1">
            {landingLinks.map((link) => (
              <button
                key={link.id}
                type="button"
                onClick={() => scrollToSection(link.id)}
                className={`px-4 py-2 text-sm rounded-full transition-colors cursor-pointer ${
                  activeSection === link.id ? 'bg-sky-700 text-white' : 'text-slate-700 hover:bg-sky-50'
                }`}
              >
                {link.label}
              </button>
            ))}
          </nav>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => jumpToAuth('login')}
              className="px-4 py-2 rounded-lg border border-sky-200 text-sky-700 text-sm font-semibold hover:bg-sky-50 transition-colors cursor-pointer"
            >
              Sign In
            </button>
            <button
              type="button"
              onClick={() => jumpToAuth('register')}
              className="px-4 py-2 rounded-lg bg-sky-700 text-white text-sm font-semibold hover:bg-sky-800 transition-colors cursor-pointer"
            >
              Register
            </button>
          </div>
        </div>
      </header>

      <main className="flex-1">
        <section id="hero" data-landing-section className="scroll-mt-28 pt-10 pb-16 sm:pt-14 lg:pt-20 lg:pb-20">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 grid lg:grid-cols-2 gap-10 items-center">
            <motion.div
              initial={{ opacity: 0, y: 22 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.6 }}
              className="space-y-8"
            >
              <div className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-sky-100/70 px-3 py-1 text-xs text-sky-700 font-semibold">
                <Sparkles className="w-3.5 h-3.5" />
                Next-generation educational RAG platform
              </div>

              <div className="space-y-5">
                <h1 className="text-4xl sm:text-5xl lg:text-6xl font-black tracking-tight leading-[1.08] [font-family:var(--font-display)] text-slate-900">
                  Smarter learning content,
                  <span className="text-sky-700"> stronger outcomes</span>.
                </h1>
                <p className="text-lg leading-8 text-slate-600 max-w-xl">
                  BK-MInD turns lecture videos, documents, and slides into a searchable knowledge space
                  for retrieval, grounded Q&A, and academic summarization.
                </p>
              </div>

              <div className="flex flex-wrap items-center gap-3">
                <button
                  type="button"
                  onClick={() => jumpToAuth('register')}
                  className="inline-flex items-center gap-2 rounded-xl bg-sky-700 px-6 py-3 text-white font-semibold hover:bg-sky-800 transition-colors cursor-pointer"
                >
                  Start for Free
                  <ArrowRight className="w-4 h-4" />
                </button>
                <button
                  type="button"
                  onClick={() => scrollToSection('features')}
                  className="inline-flex items-center gap-2 rounded-xl border border-sky-200 bg-white px-6 py-3 text-sky-700 font-semibold hover:bg-sky-50 transition-colors cursor-pointer"
                >
                  Explore Features
                  <ChevronsDown className="w-4 h-4" />
                </button>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 pt-2">
                {impactStats.map((item) => (
                  <div key={item.label} className="rounded-xl border border-sky-100 bg-white p-4 shadow-[0_10px_30px_-20px_rgba(2,132,199,0.45)]">
                    <p className="text-2xl font-black text-sky-700 [font-family:var(--font-display)]">{item.value}</p>
                    <p className="text-xs text-slate-500 mt-1 leading-5">{item.label}</p>
                  </div>
                ))}
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.65, delay: 0.12 }}
              className="relative"
            >
              <div className="rounded-3xl border border-sky-100 bg-white p-5 sm:p-8 shadow-[0_35px_80px_-45px_rgba(2,132,199,0.5)]">
                <div className="rounded-2xl bg-sky-50 border border-sky-100 p-4 sm:p-8 overflow-hidden">
                  <img
                    src={robotHeroSrc}
                    srcSet={robotHeroSrcSet}
                    sizes="(max-width: 768px) 90vw, 532px"
                    width={800}
                    height={800}
                    loading="eager"
                    fetchPriority="high"
                    decoding="async"
                    alt="BK-MInD learning assistant"
                    className="w-full h-auto max-h-[500px] object-contain mx-auto animate-float"
                  />
                </div>
                <div className="mt-6 grid grid-cols-1 sm:grid-cols-2 gap-3">
                  <div className="rounded-xl border border-sky-100 bg-sky-50 p-4">
                    <p className="text-sm font-semibold text-slate-800">AI Assistant</p>
                    <p className="text-xs text-slate-600 mt-1">Context-aware Q&A for lecture content</p>
                  </div>
                  <div className="rounded-xl border border-sky-100 bg-sky-50 p-4">
                    <p className="text-sm font-semibold text-slate-800">Smart Citation</p>
                    <p className="text-xs text-slate-600 mt-1">Clear source citations for every response</p>
                  </div>
                </div>
              </div>
            </motion.div>
          </div>
        </section>

        <section id="features" data-landing-section className="scroll-mt-28 py-16 lg:py-20 bg-white border-y border-sky-100/80">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.45 }}
              transition={{ duration: 0.55 }}
              className="max-w-2xl"
            >
              <p className="inline-flex items-center gap-2 text-sm font-semibold text-sky-700">
                <GraduationCap className="w-4 h-4" />
                Key Capabilities
              </p>
              <h2 className="mt-3 text-3xl sm:text-4xl font-black [font-family:var(--font-display)] tracking-tight text-slate-900">
                Designed for modern classrooms in Vietnam
              </h2>
              <p className="mt-4 text-slate-600 leading-7">
                From content processing to retrieval and answer generation, every step supports better learning and teaching.
              </p>
            </motion.div>

            <div className="mt-10 grid md:grid-cols-3 gap-5">
              {valueHighlights.map((item, idx) => (
                <motion.article
                  key={item.title}
                  initial={{ opacity: 0, y: 26 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.25 }}
                  transition={{ duration: 0.5, delay: idx * 0.08 }}
                  className="rounded-2xl border border-sky-100 bg-sky-50 p-6 hover:border-sky-200 hover:-translate-y-1 transition-all"
                >
                  <span className="w-11 h-11 rounded-xl bg-white border border-sky-200 flex items-center justify-center text-sky-700 mb-4">
                    <item.icon className="w-5 h-5" />
                  </span>
                  <h3 className="text-lg font-bold text-slate-900">{item.title}</h3>
                  <p className="text-sm leading-6 text-slate-600 mt-3">{item.description}</p>
                </motion.article>
              ))}
            </div>
          </div>
        </section>

        <section id="workflow" data-landing-section className="scroll-mt-28 py-16 lg:py-20">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 grid lg:grid-cols-2 gap-8 lg:gap-12 items-start">
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.35 }}
              transition={{ duration: 0.55 }}
              className="rounded-3xl border border-sky-100 bg-white p-7 lg:p-8 shadow-[0_20px_60px_-42px_rgba(14,165,233,0.55)]"
            >
              <p className="inline-flex items-center gap-2 text-sm font-semibold text-sky-700">
                <Clock3 className="w-4 h-4" />
                4-Step Workflow
              </p>
              <h2 className="mt-4 text-3xl font-black [font-family:var(--font-display)] text-slate-900 leading-tight">
                From raw content to an intelligent learning assistant
              </h2>
              <p className="text-slate-600 leading-7 mt-4">
                Start with your existing materials, and the system transforms them into query-ready knowledge.
              </p>
              <div className="mt-6 rounded-2xl border border-sky-100 bg-sky-50 p-5">
                <p className="text-sm text-slate-600">
                  Performance targets from the specification: text retrieval under 1 second, cited answers under 10 seconds.
                </p>
              </div>
            </motion.div>

            <div className="space-y-4">
              {processSteps.map((step, idx) => (
                <motion.div
                  key={step.title}
                  initial={{ opacity: 0, x: 20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true, amount: 0.25 }}
                  transition={{ duration: 0.45, delay: idx * 0.08 }}
                  className="rounded-2xl border border-sky-100 bg-white p-5 hover:border-sky-200 transition-colors"
                >
                  <h3 className="text-base font-bold text-slate-900">{step.title}</h3>
                  <p className="mt-2 text-sm leading-6 text-slate-600">{step.detail}</p>
                </motion.div>
              ))}
            </div>
          </div>
        </section>

        <section id="testimonials" data-landing-section className="scroll-mt-28 py-16 lg:py-20 bg-white border-y border-sky-100/80">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.4 }}
              transition={{ duration: 0.55 }}
              className="flex flex-col md:flex-row md:items-end md:justify-between gap-4"
            >
              <div>
                <p className="text-sm font-semibold text-sky-700">Testimonials</p>
                <h2 className="mt-2 text-3xl sm:text-4xl font-black [font-family:var(--font-display)] tracking-tight text-slate-900">
                  What students and lecturers are saying
                </h2>
              </div>
              <div className="inline-flex items-center gap-1 text-amber-500">
                <Star className="w-4 h-4 fill-current" />
                <Star className="w-4 h-4 fill-current" />
                <Star className="w-4 h-4 fill-current" />
                <Star className="w-4 h-4 fill-current" />
                <Star className="w-4 h-4 fill-current" />
                <span className="ml-2 text-sm text-slate-500">4.9/5 from pilot users</span>
              </div>
            </motion.div>

            <div className="mt-10 grid md:grid-cols-3 gap-5">
              {testimonials.map((item, idx) => (
                <motion.article
                  key={item.name}
                  initial={{ opacity: 0, y: 24 }}
                  whileInView={{ opacity: 1, y: 0 }}
                  viewport={{ once: true, amount: 0.25 }}
                  transition={{ duration: 0.5, delay: idx * 0.08 }}
                  className="rounded-2xl border border-sky-100 bg-white p-6 shadow-[0_18px_40px_-28px_rgba(14,165,233,0.45)]"
                >
                  <div className="inline-flex items-center gap-2 rounded-full bg-sky-50 border border-sky-100 px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-sky-700">
                    <Quote className="w-3.5 h-3.5" />
                    Trusted Feedback
                  </div>
                  <p className="mt-4 text-sm leading-7 text-slate-700 min-h-[120px]">{item.quote}</p>
                  <div className="mt-5 pt-4 border-t border-sky-100 flex items-center gap-3">
                    <span className="w-9 h-9 rounded-full bg-sky-100 text-sky-700 text-sm font-black flex items-center justify-center shrink-0">
                      {item.name.trim().charAt(0)}
                    </span>
                    <div className="min-w-0">
                      <p className="text-sm font-bold text-slate-900 truncate" title={item.name}>{item.name}</p>
                      <p className="text-xs text-slate-600 mt-0.5">{item.role}</p>
                    </div>
                    <span className="ml-auto rounded-full border border-emerald-200 bg-emerald-50 px-2 py-1 text-[10px] font-bold uppercase tracking-wide text-emerald-700">
                      {idx === 1 ? 'Lecturer' : 'Learner'}
                    </span>
                  </div>
                </motion.article>
              ))}
            </div>
          </div>
        </section>

        <section id="auth" data-landing-section className="scroll-mt-28 py-16 lg:py-20">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 grid lg:grid-cols-2 gap-8 lg:gap-12 items-start">
            <motion.div
              initial={{ opacity: 0, y: 18 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.35 }}
              transition={{ duration: 0.55 }}
              className="rounded-3xl border border-sky-100 bg-white p-7 lg:p-8"
            >
              <p className="text-sm font-semibold text-sky-700">Ready to get started?</p>
              <h2 className="mt-3 text-3xl font-black [font-family:var(--font-display)] text-slate-900 leading-tight">
                Sign in to build your personal learning knowledge hub.
              </h2>
              <p className="mt-4 text-slate-600 leading-7">
                BK-MInD supports both self-learning students and lecturers who need fast organization,
                retrieval, and content verification.
              </p>

              <div className="mt-7 space-y-4">
                <div className="flex items-start gap-3 text-sm text-slate-700">
                  <CheckCircle2 className="w-5 h-5 text-emerald-500 mt-0.5" />
                  Automatic syncing of documents and processing status
                </div>
                <div className="flex items-start gap-3 text-sm text-slate-700">
                  <CheckCircle2 className="w-5 h-5 text-emerald-500 mt-0.5" />
                  Search and chat with transparent source citations
                </div>
                <div className="flex items-start gap-3 text-sm text-slate-700">
                  <CheckCircle2 className="w-5 h-5 text-emerald-500 mt-0.5" />
                  Long-term learning progress support
                </div>
              </div>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 22 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true, amount: 0.25 }}
              transition={{ duration: 0.55 }}
              className="rounded-3xl border border-sky-100 bg-white p-6 sm:p-7 shadow-[0_24px_70px_-50px_rgba(2,132,199,0.55)]"
            >
              <div className="flex items-center justify-between gap-3 mb-5">
                <h3 className="text-2xl font-black [font-family:var(--font-display)] text-slate-900">BK-MInD Account</h3>
                <span className="rounded-full bg-sky-100 text-sky-700 text-xs px-3 py-1 font-semibold">Secure Access</span>
              </div>

              <div className="grid grid-cols-2 gap-2 p-1 rounded-xl bg-sky-50 border border-sky-100 mb-5">
                <button
                  type="button"
                  onClick={() => setAuthMode('login')}
                  className={`py-2.5 rounded-lg text-sm font-semibold transition-colors cursor-pointer ${
                    authMode === 'login' ? 'bg-white text-sky-700 shadow-sm' : 'text-slate-600 hover:text-slate-800'
                  }`}
                >
                  <span className="inline-flex items-center gap-2">
                    <LogIn className="w-4 h-4" />
                    Sign In
                  </span>
                </button>
                <button
                  type="button"
                  onClick={() => setAuthMode('register')}
                  className={`py-2.5 rounded-lg text-sm font-semibold transition-colors cursor-pointer ${
                    authMode === 'register' ? 'bg-white text-sky-700 shadow-sm' : 'text-slate-600 hover:text-slate-800'
                  }`}
                >
                  <span className="inline-flex items-center gap-2">
                    <UserPlus className="w-4 h-4" />
                    Register
                  </span>
                </button>
              </div>

              <AnimatePresence mode="wait">
                {error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="mb-4 rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600"
                  >
                    {error}
                  </motion.div>
                )}
              </AnimatePresence>

              <button
                onClick={handleGoogleSignIn}
                disabled={isLoading}
                className="group w-full flex items-center justify-center gap-3 rounded-xl border border-slate-200 bg-white py-3.5 px-4 text-sm font-semibold text-slate-700 hover:bg-slate-50 transition-colors disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {isLoading ? (
                  <Loader2 className="w-5 h-5 animate-spin text-sky-600" />
                ) : (
                  <>
                    <svg className="w-5 h-5" viewBox="0 0 24 24" aria-hidden="true">
                      <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4" />
                      <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853" />
                      <path d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z" fill="#FBBC05" />
                      <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z" fill="#EA4335" />
                    </svg>
                    Continue with Google
                  </>
                )}
              </button>

              <div className="relative my-5">
                <div className="absolute inset-0 flex items-center">
                  <div className="w-full border-t border-slate-200" />
                </div>
                <div className="relative flex justify-center">
                  <span className="bg-white px-3 text-xs text-slate-400 uppercase tracking-widest">or</span>
                </div>
              </div>

              <div className="space-y-3">
                <input
                  type="email"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full rounded-xl border border-sky-200 bg-sky-50/70 px-3.5 py-3 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 transition-all"
                />
                <input
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full rounded-xl border border-sky-200 bg-sky-50/70 px-3.5 py-3 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 transition-all"
                />
                {authMode === 'register' && (
                  <input
                    type="text"
                    placeholder="Display name"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    className="w-full rounded-xl border border-sky-200 bg-sky-50/70 px-3.5 py-3 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-500/20 transition-all"
                  />
                )}
              </div>

              <button
                onClick={() => {
                  if (authMode === 'login') {
                    void handleLocalLogin();
                    return;
                  }
                  void handleLocalRegister();
                }}
                disabled={isLoading || !email || !password || (authMode === 'register' && !displayName.trim())}
                className="mt-4 w-full rounded-xl bg-sky-700 py-3 text-sm font-semibold text-white hover:bg-sky-800 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {authMode === 'login' ? 'Sign in with app account' : 'Create new account'}
              </button>

              <div className="mt-5 pt-4 border-t border-slate-100 flex items-center justify-center gap-2 text-xs text-slate-600">
                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                Login data is protected and handled securely.
              </div>
            </motion.div>
          </div>
        </section>

        <div className="pb-10 flex justify-center">
          <button
            type="button"
            onClick={() => scrollToSection('features')}
            className="inline-flex items-center gap-2 rounded-full border border-sky-200 bg-white px-4 py-2 text-sm text-sky-700 hover:bg-sky-50 transition-colors cursor-pointer"
          >
            <Zap className="w-4 h-4" />
            Scroll up to explore more features
          </button>
        </div>
      </main>

      <AppFooter className="border-sky-200/80 bg-white/95" />
    </div>
  );
}
