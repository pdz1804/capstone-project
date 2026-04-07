import { useState } from 'react';
import {
  BookOpen,
  LogIn,
  Loader2,
  CheckCircle2,
  Sparkles,
  Database,
  Zap,
  ArrowRight
} from 'lucide-react';
import { motion, AnimatePresence } from 'motion/react';
import { authService } from '../services/auth_service';

export default function LoginView() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleGoogleSignIn = async () => {
    setIsLoading(true);
    setError(null);
    try {
      await authService.login();
    } catch (err: any) {
      setError(err.message || "Failed to sign in. Please try again.");
      setIsLoading(false);
    }
  };

  const features = [
    { icon: Database, text: "Advanced RAG indexing for your educational content" },
    { icon: Zap, text: "Instant transcription and semantic search" },
    { icon: Sparkles, text: "AI-powered learning paths and quiz generation" },
  ];

  return (
    <div className="min-h-screen flex bg-white overflow-hidden">
      {/* Left Side: Visual & Marketing */}
      <div className="hidden lg:flex lg:w-1/2 relative bg-sky-600 items-center justify-center overflow-hidden">
        {/* Animated Background Elements */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute -top-[10%] -left-[10%] w-[60%] h-[60%] bg-sky-500 rounded-full blur-[120px] opacity-50 animate-pulse" />
          <div className="absolute -bottom-[10%] -right-[10%] w-[60%] h-[60%] bg-blue-400 rounded-full blur-[120px] opacity-40 animate-pulse" style={{ animationDelay: '2s' }} />
          <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full h-full bg-[radial-gradient(circle_at_center,transparent_0%,rgba(79,70,229,0.4)_100%)]" />
        </div>

        {/* Content Container */}
        <div className="relative z-10 max-w-lg px-12 text-white">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 backdrop-blur-md border border-white/20 text-sky-100 text-xs font-medium mb-8">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Next Generation Learning</span>
            </div>

            <h1 className="text-5xl font-extrabold tracking-tight mb-6 leading-[1.1]">
              Unlock the full potential of your <span className="text-blue-200">knowledge</span>.
            </h1>

            <p className="text-lg text-sky-100/80 mb-12 leading-relaxed">
              BK-MInD uses state-of-the-art AI to transform your lecture notes, videos, and documents into an interactive, searchable knowledge base.
            </p>

            <div className="space-y-6">
              {features.map((feature, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.4 + idx * 0.1 }}
                  className="flex items-center gap-4 group"
                >
                  <div className="w-10 h-10 rounded-xl bg-white/10 backdrop-blur-md border border-white/20 flex items-center justify-center group-hover:bg-white/20 transition-colors">
                    <feature.icon className="w-5 h-5 text-blue-200" />
                  </div>
                  <span className="text-sky-50 font-medium">{feature.text}</span>
                </motion.div>
              ))}
            </div>
          </motion.div>

          {/* Floating Decorative Elements */}
          <div className="absolute -top-24 -right-24 w-48 h-48 bg-white/5 rounded-full border border-white/10 animate-float" />
          <div className="absolute -bottom-12 -left-12 w-32 h-32 bg-white/5 rounded-full border border-white/10 animate-float-delayed" />
        </div>
      </div>

      {/* Right Side: Login Form */}
      <div className="w-full lg:w-1/2 flex flex-col items-center justify-center px-6 sm:px-12 lg:px-24">
        <div className="w-full max-w-md">
          {/* Logo (Mobile Only) */}
          <div className="lg:hidden flex justify-center mb-12">
            <div className="w-12 h-12 rounded-xl bg-sky-600 flex items-center justify-center shadow-lg shadow-sky-200">
              <BookOpen className="w-7 h-7 text-white" />
            </div>
          </div>

          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}
          >
            <div className="mb-10">
              <h2 className="text-3xl font-bold text-slate-900 tracking-tight mb-3">
                Welcome back
              </h2>
              <p className="text-slate-500">
                Sign in to continue your learning journey with BK-MInD.
              </p>
            </div>

            <div className="space-y-6">
              <AnimatePresence mode="wait">
                {error && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    className="p-4 bg-red-50 border border-red-100 text-red-600 rounded-xl text-sm flex items-start gap-3"
                  >
                    <div className="mt-0.5">
                      <LogIn className="w-4 h-4" />
                    </div>
                    <p>{error}</p>
                  </motion.div>
                )}
              </AnimatePresence>

              <button
                onClick={handleGoogleSignIn}
                disabled={isLoading}
                className="group relative w-full flex justify-center items-center gap-3 py-4 px-4 border border-slate-200 rounded-2xl shadow-sm bg-white text-base font-semibold text-slate-700 hover:bg-slate-50 hover:border-sky-300 focus:outline-none focus:ring-4 focus:ring-sky-500/10 transition-all disabled:opacity-50 disabled:cursor-not-allowed overflow-hidden active:scale-[0.98]"
              >
                {isLoading ? (
                  <Loader2 className="w-6 h-6 animate-spin text-sky-600" />
                ) : (
                  <>
                    <svg className="w-6 h-6" viewBox="0 0 24 24">
                      <path
                        d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
                        fill="#4285F4"
                      />
                      <path
                        d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
                        fill="#34A853"
                      />
                      <path
                        d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
                        fill="#FBBC05"
                      />
                      <path
                        d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
                        fill="#EA4335"
                      />
                    </svg>
                    <span>Continue with Google</span>
                    <ArrowRight className="w-5 h-5 ml-auto text-slate-300 group-hover:text-sky-500 group-hover:translate-x-1 transition-all" />
                  </>
                )}
              </button>

              <div className="pt-6">
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-slate-100" />
                  </div>
                  <div className="relative flex justify-center text-xs">
                    <span className="px-4 bg-white text-slate-400 font-medium uppercase tracking-wider">
                      Secure Access
                    </span>
                  </div>
                </div>

                <div className="mt-8 flex items-center justify-center gap-2 text-slate-400 text-sm">
                  <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                  <span>Registration is automatic and secure</span>
                </div>
              </div>
            </div>
          </motion.div>

          {/* Footer */}
          <div className="mt-auto pt-24 text-center">
            <p className="text-xs text-slate-400">
              By continuing, you agree to BK-MInD's <br />
              <button className="text-slate-600 hover:text-sky-600 underline underline-offset-4">Terms of Service</button> and <button className="text-slate-600 hover:text-sky-600 underline underline-offset-4">Privacy Policy</button>.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
