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
import AppFooter from '../components/AppFooter';

export default function LoginView() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');

  const handleGoogleSignIn = async () => {
    setIsLoading(true);
    setError(null);
    try {
      await authService.login();
    } catch (err: any) {
      setError(err.message || "Failed to sign in. Please try again.");
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
      setError(err?.response?.data?.detail || err.message || 'Failed to register');
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
      setError(err?.response?.data?.detail || err.message || 'Failed to login');
    } finally {
      setIsLoading(false);
    }
  };

  const features = [
    { icon: Database, text: "Advanced RAG indexing for your educational content" },
    { icon: Zap, text: "Instant transcription and semantic search" },
    { icon: Sparkles, text: "AI-powered learning paths and quiz generation" },
  ];

  return (
    <div className="min-h-screen flex flex-col bg-sky-50">
      <div className="flex-1 flex overflow-hidden min-h-0">
      {/* Left Side: Visual & Marketing */}
      <div className="hidden lg:flex lg:w-1/2 relative bg-sky-600 items-center justify-center overflow-hidden">
        {/* Animated Background Elements */}
        <div className="absolute inset-0 overflow-hidden">
          <div className="absolute inset-0 bg-white/5" />
          <div className="absolute inset-0 opacity-20 [background-image:linear-gradient(rgba(255,255,255,0.25)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.25)_1px,transparent_1px)] [background-size:48px_48px]" />
        </div>

        {/* Content Container */}
        <div className="relative z-10 max-w-lg px-12 text-white">
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.6 }}
          >
            <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/20 backdrop-blur-md border border-white/35 text-white text-xs font-medium mb-8 shadow-sm">
              <Sparkles className="w-3.5 h-3.5" />
              <span>Next Generation Learning</span>
            </div>
            
            <h1 className="text-5xl font-extrabold tracking-tight mb-6 leading-[1.1]">
              Unlock the full potential of your <span className="text-cyan-100">knowledge</span>.
            </h1>
            
            <p className="text-lg text-sky-100/95 mb-12 leading-relaxed">
              BK-MInD uses state-of-the-art AI to transform your lecture notes, videos, and documents into an interactive, searchable knowledge base.
            </p>

            <div className="space-y-6">
              {features.map((feature, idx) => (
                <motion.div
                  key={idx}
                  initial={{ opacity: 0, x: -20 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: 0.4 + idx * 0.1 }}
                  whileHover={{ x: 6 }}
                  className="flex items-center gap-4 group"
                >
                  <div className="w-10 h-10 rounded-lg bg-white/20 border border-white/30 flex items-center justify-center group-hover:bg-white/30 transition-colors">
                    <feature.icon className="w-5 h-5 text-sky-100" />
                  </div>
                  <span className="text-sky-50 font-medium">{feature.text}</span>
                </motion.div>
              ))}
            </div>
          </motion.div>

        </div>
      </div>

      {/* Right Side: Login Form */}
      <div className="w-full lg:w-1/2 flex flex-col items-center justify-center px-6 sm:px-12 lg:px-24 relative bg-sky-50">
        <div className="w-full max-w-md">
          {/* Logo (Mobile Only) */}
          <div className="lg:hidden flex justify-center mb-12">
            <div className="w-12 h-12 rounded-lg bg-sky-600 flex items-center justify-center shadow-md">
              <BookOpen className="w-7 h-7 text-white" />
            </div>
          </div>

          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.4 }}
            whileHover={{ y: -2 }}
            className="relative z-10 rounded-xl bg-white border border-sky-100 shadow-lg px-6 py-7 sm:px-8"
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
                className="group relative w-full flex justify-center items-center gap-3 py-3.5 px-4 border border-slate-200 rounded-lg shadow-sm bg-white text-sm font-semibold text-slate-700 hover:bg-slate-50 hover:border-slate-300 focus:outline-none focus:ring-2 focus:ring-blue-600/20 transition-all disabled:opacity-50 disabled:cursor-not-allowed active:scale-[0.98]"
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
                    <ArrowRight className="w-5 h-5 ml-auto text-slate-300 group-hover:text-sky-600 group-hover:translate-x-1 transition-all" />
                  </>
                )}
              </button>

              <div className="rounded-lg border border-sky-200 bg-sky-50 p-4 space-y-3">
                <p className="text-sm font-medium text-slate-700">Or sign in with app account</p>
                <input
                  type="email"
                  placeholder="Email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-lg border border-sky-300 bg-white transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-sky-700/30 focus:border-sky-600"
                />
                <input
                  type="password"
                  placeholder="Password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-lg border border-sky-300 bg-white transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-sky-700/30 focus:border-sky-600"
                />
                <input
                  type="text"
                  placeholder="Display name (for Register)"
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  className="w-full px-3 py-2.5 rounded-lg border border-sky-300 bg-white transition-all duration-200 focus:outline-none focus:ring-2 focus:ring-sky-700/30 focus:border-sky-600"
                />
                <div className="flex items-center gap-2">
                  <button
                    onClick={handleLocalLogin}
                    disabled={isLoading || !email || !password}
                    className="flex-1 py-2.5 rounded-lg bg-sky-600 text-white text-sm font-medium hover:bg-sky-700 transition-colors disabled:opacity-50"
                  >
                    Login
                  </button>
                  <button
                    onClick={handleLocalRegister}
                    disabled={isLoading || !email || !password}
                    className="flex-1 py-2.5 rounded-lg border border-sky-300 text-sky-700 text-sm font-medium hover:bg-sky-100/70 transition-colors disabled:opacity-50"
                  >
                    Register
                  </button>
                </div>
              </div>

              <div className="pt-6">
                <div className="relative">
                  <div className="absolute inset-0 flex items-center">
                    <div className="w-full border-t border-slate-100" />
                  </div>
                  <div className="relative flex justify-center text-xs">
                    <span className="px-4 bg-white/90 text-slate-400 font-medium uppercase tracking-wider">
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
          <div className="mt-auto pt-10 text-center">
            <p className="text-xs text-slate-400">
              By continuing, you agree to BK-MInD's <br />
              <button className="text-slate-600 hover:text-sky-600 underline underline-offset-4">Terms of Service</button> and <button className="text-slate-600 hover:text-sky-600 underline underline-offset-4">Privacy Policy</button>.
            </p>
          </div>
        </div>
      </div>
      </div>
      <AppFooter className="bg-white/95 backdrop-blur-sm border-slate-200/80" />
    </div>
  );
}
