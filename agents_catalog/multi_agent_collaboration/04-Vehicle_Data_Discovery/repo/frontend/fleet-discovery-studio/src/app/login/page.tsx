"use client"

import { useState } from 'react'
import { motion } from 'framer-motion'
import '@/lib/auth-config' // Must be imported before any auth calls
import { signIn, signUp, resetPassword, confirmResetPassword, confirmSignUp } from 'aws-amplify/auth'
import { Eye, EyeOff, Lock, Mail, Zap, AlertCircle, Sparkles, ArrowLeft, UserPlus, KeyRound, CheckCircle } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card } from '@/components/ui/card'

type AuthMode = 'signin' | 'signup' | 'forgot' | 'verify' | 'reset'

export default function LoginPage() {
  const [mode, setMode] = useState<AuthMode>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [verificationCode, setVerificationCode] = useState('')
  const [resetCode, setResetCode] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')
  const [success, setSuccess] = useState('')

  const clearMessages = () => {
    setError('')
    setSuccess('')
  }

  const handleSignIn = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    clearMessages()

    try {
      const { isSignedIn, nextStep } = await signIn({ username: email, password })
      console.log('Sign in result:', { isSignedIn, nextStep })
      
      if (isSignedIn) {
        window.location.href = '/'
      } else {
        console.log('Additional step required:', nextStep)
        setError('Additional authentication step required')
      }
    } catch (err: any) {
      console.error('Sign in error:', err)
      const errorMessage = err.message || 'Authentication failed'

      if (errorMessage.includes('UserNotFoundException')) {
        setError('No account found with this email address')
      } else if (errorMessage.includes('NotAuthorizedException')) {
        setError('Invalid email or password')
      } else if (errorMessage.includes('UserNotConfirmedException')) {
        setError('Please check your email and verify your account first')
        setMode('verify')
      } else {
        setError('Authentication failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleSignUp = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    clearMessages()

    if (password !== confirmPassword) {
      setError('Passwords do not match')
      setLoading(false)
      return
    }

    try {
      await signUp({
        username: email,
        password,
        options: {
          userAttributes: { email }
        }
      })
      setSuccess('Account created! Please check your email for verification code.')
      setMode('verify')
    } catch (err: any) {
      console.error('Sign up error:', err)
      const errorMessage = err.message || 'Sign up failed'

      if (errorMessage.includes('UsernameExistsException')) {
        setError('An account with this email already exists')
      } else if (errorMessage.includes('InvalidPasswordException')) {
        setError('Password must be at least 8 characters with uppercase, lowercase, number and symbol')
      } else {
        setError('Sign up failed. Please try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  const handleVerifyEmail = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    clearMessages()

    try {
      await confirmSignUp({ username: email, confirmationCode: verificationCode })
      setSuccess('Email verified! You can now sign in.')
      setMode('signin')
      setVerificationCode('')
    } catch (err: any) {
      console.error('Verification error:', err)
      setError('Invalid verification code. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleForgotPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    clearMessages()

    try {
      await resetPassword({ username: email })
      setSuccess('Password reset code sent to your email.')
      setMode('reset')
    } catch (err: any) {
      console.error('Forgot password error:', err)
      setError('Failed to send reset code. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    clearMessages()

    try {
      await confirmResetPassword({
        username: email,
        confirmationCode: resetCode,
        newPassword
      })
      setSuccess('Password reset successfully! You can now sign in.')
      setMode('signin')
      setResetCode('')
      setNewPassword('')
    } catch (err: any) {
      console.error('Reset password error:', err)
      setError('Invalid reset code or password. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen relative overflow-hidden bg-gradient-to-br from-[var(--deep-charcoal)] via-gray-900 to-black">

      {/* Neural Horizon Background - Apple-Grade Cinematic Effect */}
      <div className="absolute inset-0 overflow-hidden">
        {/* Animated Neural Particles */}
        <div className="absolute inset-0">
          {[...Array(50)].map((_, i) => (
            <motion.div
              key={i}
              className="absolute w-1 h-1 bg-[var(--cyber-blue)] rounded-full opacity-60"
              style={{
                left: `${Math.random() * 100}%`,
                top: `${Math.random() * 100}%`,
              }}
              animate={{
                opacity: [0.2, 0.8, 0.2],
                scale: [1, 1.5, 1],
              }}
              transition={{
                duration: 3 + Math.random() * 2,
                repeat: Infinity,
                delay: Math.random() * 2,
              }}
            />
          ))}
        </div>

        {/* Flowing Neural Connections */}
        <div className="absolute inset-0">
          <svg className="w-full h-full">
            <defs>
              <linearGradient id="neuralGradient" x1="0%" y1="0%" x2="100%" y2="100%">
                <stop offset="0%" stopColor="var(--cyber-blue)" stopOpacity="0.1"/>
                <stop offset="50%" stopColor="#8B5CF6" stopOpacity="0.3"/>
                <stop offset="100%" stopColor="var(--cyber-blue)" stopOpacity="0.1"/>
              </linearGradient>
            </defs>
            {[...Array(8)].map((_, i) => (
              <motion.path
                key={i}
                d={`M ${Math.random() * 100} ${Math.random() * 100} Q ${Math.random() * 100} ${Math.random() * 100} ${Math.random() * 100} ${Math.random() * 100}`}
                stroke="url(#neuralGradient)"
                strokeWidth="1"
                fill="none"
                initial={{ pathLength: 0, opacity: 0 }}
                animate={{ pathLength: 1, opacity: 0.6 }}
                transition={{
                  duration: 4 + Math.random() * 3,
                  repeat: Infinity,
                  repeatType: "reverse",
                  delay: Math.random() * 2,
                }}
              />
            ))}
          </svg>
        </div>

        {/* Gaussian Blur Overlay for Depth */}
        <div className="absolute inset-0 bg-black/40 backdrop-blur-[1px]" />
      </div>

      {/* Main Content */}
      <div className="relative z-10 flex items-center justify-center min-h-screen p-4">
        <motion.div
          initial={{ opacity: 0, y: 30, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          transition={{ duration: 1, ease: "easeOut" }}
          className="w-full max-w-md"
        >

          {/* Fleet Branding - Cinematic Entry */}
          <motion.div
            initial={{ opacity: 0, y: -20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.3 }}
            className="text-center mb-8"
          >
            <motion.div
              initial={{ scale: 0.8, rotate: -5 }}
              animate={{ scale: 1, rotate: 0 }}
              transition={{ duration: 0.6, delay: 0.5 }}
              className="relative w-20 h-20 mx-auto mb-6"
            >
              {/* Glowing Background */}
              <div className="absolute inset-0 bg-gradient-to-r from-[var(--cyber-blue)] to-purple-500 rounded-2xl blur-lg opacity-60" />

              {/* Icon Container */}
              <div className="relative w-full h-full bg-gradient-to-r from-[var(--cyber-blue)] to-purple-500 rounded-2xl flex items-center justify-center shadow-2xl">
                <Zap className="w-10 h-10 text-white" />

                {/* Sparkle Effects */}
                <motion.div
                  className="absolute -top-1 -right-1"
                  animate={{ rotate: 360 }}
                  transition={{ duration: 8, repeat: Infinity, ease: "linear" }}
                >
                  <Sparkles className="w-4 h-4 text-white/80" />
                </motion.div>
              </div>
            </motion.div>

            <motion.h1
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.7 }}
              className="text-3xl font-bold bg-gradient-to-r from-white via-gray-100 to-white bg-clip-text text-transparent mb-3"
            >
              Fleet Discovery
            </motion.h1>
            <motion.p
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              transition={{ delay: 0.9 }}
              className="text-white/60 text-sm leading-relaxed"
            >
              Intelligence-grade autonomous driving insights
              <br />
              <span className="text-[var(--cyber-blue)]/80">Neural • Forensic • Discovery</span>
            </motion.p>
          </motion.div>

          {/* Apple-Style Glassmorphic Auth Card */}
          <motion.div
            key={mode} // Key ensures smooth transitions between modes
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -20 }}
            transition={{ duration: 0.5 }}
          >
            <Card className="p-8 bg-white/10 backdrop-blur-xl border border-white/20 shadow-2xl">

              {/* Mode Header */}
              <div className="mb-6 text-center">
                <motion.div
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="flex items-center justify-center gap-2 mb-2"
                >
                  {mode === 'signin' && <Zap className="w-5 h-5 text-[var(--cyber-blue)]" />}
                  {mode === 'signup' && <UserPlus className="w-5 h-5 text-[var(--cyber-blue)]" />}
                  {mode === 'forgot' && <KeyRound className="w-5 h-5 text-[var(--cyber-blue)]" />}
                  {mode === 'verify' && <CheckCircle className="w-5 h-5 text-[var(--cyber-blue)]" />}
                  {mode === 'reset' && <Lock className="w-5 h-5 text-[var(--cyber-blue)]" />}

                  <h2 className="text-xl font-semibold text-white">
                    {mode === 'signin' && 'Sign In'}
                    {mode === 'signup' && 'Create Account'}
                    {mode === 'forgot' && 'Reset Password'}
                    {mode === 'verify' && 'Verify Email'}
                    {mode === 'reset' && 'New Password'}
                  </h2>
                </motion.div>

                {mode !== 'signin' && (
                  <button
                    onClick={() => setMode('signin')}
                    className="flex items-center gap-1 text-sm text-white/60 hover:text-white/90 transition-colors mx-auto"
                  >
                    <ArrowLeft className="w-4 h-4" />
                    Back to Sign In
                  </button>
                )}
              </div>

              {/* Dynamic Forms */}
              {mode === 'signin' && (
                <form onSubmit={handleSignIn} className="space-y-6">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-white/90">Email Address</label>
                    <div className="relative group">
                      <Mail className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-white/40 group-focus-within:text-[var(--cyber-blue)] transition-colors" />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="w-full pl-12 pr-4 py-4 rounded-xl bg-white/10 border border-white/20 focus:border-[var(--cyber-blue)] focus:ring-2 focus:ring-[var(--cyber-blue)]/30 transition-all duration-300 text-white placeholder-white/40"
                        placeholder="Enter your email"
                        required
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-white/90">Password</label>
                    <div className="relative group">
                      <Lock className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-white/40 group-focus-within:text-[var(--cyber-blue)] transition-colors" />
                      <input
                        type={showPassword ? "text" : "password"}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full pl-12 pr-14 py-4 rounded-xl bg-white/10 border border-white/20 focus:border-[var(--cyber-blue)] focus:ring-2 focus:ring-[var(--cyber-blue)]/30 transition-all duration-300 text-white placeholder-white/40"
                        placeholder="Enter your password"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-4 top-1/2 transform -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors"
                      >
                        {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                      </button>
                    </div>
                  </div>

                  <Button
                    type="submit"
                    disabled={loading}
                    className="w-full py-4 bg-gradient-to-r from-[var(--cyber-blue)] via-blue-500 to-purple-500 hover:from-[var(--cyber-blue)]/90 hover:via-blue-500/90 hover:to-purple-500/90 text-white font-semibold rounded-xl transition-all duration-300 shadow-lg hover:shadow-xl disabled:opacity-50"
                  >
                    {loading ? (
                      <div className="flex items-center justify-center gap-3">
                        <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Signing In...
                      </div>
                    ) : (
                      <div className="flex items-center justify-center gap-2">
                        <Zap className="w-5 h-5" />
                        Access Fleet Discovery
                      </div>
                    )}
                  </Button>

                  <div className="flex justify-between text-sm">
                    <button
                      type="button"
                      onClick={() => setMode('signup')}
                      className="text-[var(--cyber-blue)] hover:text-blue-300 transition-colors"
                    >
                      Create Account
                    </button>
                    <button
                      type="button"
                      onClick={() => setMode('forgot')}
                      className="text-[var(--cyber-blue)] hover:text-blue-300 transition-colors"
                    >
                      Forgot Password?
                    </button>
                  </div>
                </form>
              )}

              {mode === 'signup' && (
                <form onSubmit={handleSignUp} className="space-y-6">
                  <div className="space-y-2">
                    <label className="text-sm font-medium text-white/90">Email Address</label>
                    <div className="relative group">
                      <Mail className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-white/40 group-focus-within:text-[var(--cyber-blue)] transition-colors" />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="w-full pl-12 pr-4 py-4 rounded-xl bg-white/10 border border-white/20 focus:border-[var(--cyber-blue)] focus:ring-2 focus:ring-[var(--cyber-blue)]/30 transition-all duration-300 text-white placeholder-white/40"
                        placeholder="Enter your email"
                        required
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-white/90">Password</label>
                    <div className="relative group">
                      <Lock className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-white/40 group-focus-within:text-[var(--cyber-blue)] transition-colors" />
                      <input
                        type={showPassword ? "text" : "password"}
                        value={password}
                        onChange={(e) => setPassword(e.target.value)}
                        className="w-full pl-12 pr-14 py-4 rounded-xl bg-white/10 border border-white/20 focus:border-[var(--cyber-blue)] focus:ring-2 focus:ring-[var(--cyber-blue)]/30 transition-all duration-300 text-white placeholder-white/40"
                        placeholder="Create a password"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-4 top-1/2 transform -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors"
                      >
                        {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                      </button>
                    </div>
                    <p className="text-xs text-white/50">8+ chars with uppercase, lowercase, number & symbol</p>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-white/90">Confirm Password</label>
                    <div className="relative group">
                      <Lock className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-white/40 group-focus-within:text-[var(--cyber-blue)] transition-colors" />
                      <input
                        type="password"
                        value={confirmPassword}
                        onChange={(e) => setConfirmPassword(e.target.value)}
                        className="w-full pl-12 pr-4 py-4 rounded-xl bg-white/10 border border-white/20 focus:border-[var(--cyber-blue)] focus:ring-2 focus:ring-[var(--cyber-blue)]/30 transition-all duration-300 text-white placeholder-white/40"
                        placeholder="Confirm your password"
                        required
                      />
                    </div>
                  </div>

                  <Button
                    type="submit"
                    disabled={loading}
                    className="w-full py-4 bg-gradient-to-r from-green-500 via-emerald-500 to-teal-500 hover:from-green-500/90 hover:via-emerald-500/90 hover:to-teal-500/90 text-white font-semibold rounded-xl transition-all duration-300 shadow-lg hover:shadow-xl disabled:opacity-50"
                  >
                    {loading ? (
                      <div className="flex items-center justify-center gap-3">
                        <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Creating Account...
                      </div>
                    ) : (
                      <div className="flex items-center justify-center gap-2">
                        <UserPlus className="w-5 h-5" />
                        Create Account
                      </div>
                    )}
                  </Button>
                </form>
              )}

              {mode === 'forgot' && (
                <form onSubmit={handleForgotPassword} className="space-y-6">
                  <div className="text-center mb-4">
                    <p className="text-sm text-white/70">Enter your email to receive a password reset code</p>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-white/90">Email Address</label>
                    <div className="relative group">
                      <Mail className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-white/40 group-focus-within:text-[var(--cyber-blue)] transition-colors" />
                      <input
                        type="email"
                        value={email}
                        onChange={(e) => setEmail(e.target.value)}
                        className="w-full pl-12 pr-4 py-4 rounded-xl bg-white/10 border border-white/20 focus:border-[var(--cyber-blue)] focus:ring-2 focus:ring-[var(--cyber-blue)]/30 transition-all duration-300 text-white placeholder-white/40"
                        placeholder="Enter your email"
                        required
                      />
                    </div>
                  </div>

                  <Button
                    type="submit"
                    disabled={loading}
                    className="w-full py-4 bg-gradient-to-r from-amber-500 via-orange-500 to-red-500 hover:from-amber-500/90 hover:via-orange-500/90 hover:to-red-500/90 text-white font-semibold rounded-xl transition-all duration-300 shadow-lg hover:shadow-xl disabled:opacity-50"
                  >
                    {loading ? (
                      <div className="flex items-center justify-center gap-3">
                        <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Sending Code...
                      </div>
                    ) : (
                      <div className="flex items-center justify-center gap-2">
                        <KeyRound className="w-5 h-5" />
                        Send Reset Code
                      </div>
                    )}
                  </Button>
                </form>
              )}

              {mode === 'verify' && (
                <form onSubmit={handleVerifyEmail} className="space-y-6">
                  <div className="text-center mb-4">
                    <p className="text-sm text-white/70">Enter the verification code sent to your email</p>
                    <p className="text-xs text-white/50 mt-1">{email}</p>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-white/90">Verification Code</label>
                    <div className="relative group">
                      <CheckCircle className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-white/40 group-focus-within:text-[var(--cyber-blue)] transition-colors" />
                      <input
                        type="text"
                        value={verificationCode}
                        onChange={(e) => setVerificationCode(e.target.value)}
                        className="w-full pl-12 pr-4 py-4 rounded-xl bg-white/10 border border-white/20 focus:border-[var(--cyber-blue)] focus:ring-2 focus:ring-[var(--cyber-blue)]/30 transition-all duration-300 text-white placeholder-white/40 text-center text-lg tracking-widest"
                        placeholder="000000"
                        maxLength={6}
                        required
                      />
                    </div>
                  </div>

                  <Button
                    type="submit"
                    disabled={loading}
                    className="w-full py-4 bg-gradient-to-r from-[var(--cyber-blue)] via-blue-500 to-purple-500 hover:from-[var(--cyber-blue)]/90 hover:via-blue-500/90 hover:to-purple-500/90 text-white font-semibold rounded-xl transition-all duration-300 shadow-lg hover:shadow-xl disabled:opacity-50"
                  >
                    {loading ? (
                      <div className="flex items-center justify-center gap-3">
                        <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Verifying...
                      </div>
                    ) : (
                      <div className="flex items-center justify-center gap-2">
                        <CheckCircle className="w-5 h-5" />
                        Verify Email
                      </div>
                    )}
                  </Button>
                </form>
              )}

              {mode === 'reset' && (
                <form onSubmit={handleResetPassword} className="space-y-6">
                  <div className="text-center mb-4">
                    <p className="text-sm text-white/70">Enter the reset code and your new password</p>
                    <p className="text-xs text-white/50 mt-1">{email}</p>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-white/90">Reset Code</label>
                    <div className="relative group">
                      <KeyRound className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-white/40 group-focus-within:text-[var(--cyber-blue)] transition-colors" />
                      <input
                        type="text"
                        value={resetCode}
                        onChange={(e) => setResetCode(e.target.value)}
                        className="w-full pl-12 pr-4 py-4 rounded-xl bg-white/10 border border-white/20 focus:border-[var(--cyber-blue)] focus:ring-2 focus:ring-[var(--cyber-blue)]/30 transition-all duration-300 text-white placeholder-white/40 text-center text-lg tracking-widest"
                        placeholder="000000"
                        maxLength={6}
                        required
                      />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <label className="text-sm font-medium text-white/90">New Password</label>
                    <div className="relative group">
                      <Lock className="absolute left-4 top-1/2 transform -translate-y-1/2 w-5 h-5 text-white/40 group-focus-within:text-[var(--cyber-blue)] transition-colors" />
                      <input
                        type={showPassword ? "text" : "password"}
                        value={newPassword}
                        onChange={(e) => setNewPassword(e.target.value)}
                        className="w-full pl-12 pr-14 py-4 rounded-xl bg-white/10 border border-white/20 focus:border-[var(--cyber-blue)] focus:ring-2 focus:ring-[var(--cyber-blue)]/30 transition-all duration-300 text-white placeholder-white/40"
                        placeholder="Enter new password"
                        required
                      />
                      <button
                        type="button"
                        onClick={() => setShowPassword(!showPassword)}
                        className="absolute right-4 top-1/2 transform -translate-y-1/2 text-white/40 hover:text-white/70 transition-colors"
                      >
                        {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                      </button>
                    </div>
                  </div>

                  <Button
                    type="submit"
                    disabled={loading}
                    className="w-full py-4 bg-gradient-to-r from-green-500 via-emerald-500 to-teal-500 hover:from-green-500/90 hover:via-emerald-500/90 hover:to-teal-500/90 text-white font-semibold rounded-xl transition-all duration-300 shadow-lg hover:shadow-xl disabled:opacity-50"
                  >
                    {loading ? (
                      <div className="flex items-center justify-center gap-3">
                        <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                        Resetting Password...
                      </div>
                    ) : (
                      <div className="flex items-center justify-center gap-2">
                        <Lock className="w-5 h-5" />
                        Reset Password
                      </div>
                    )}
                  </Button>
                </form>
              )}

              {/* Error and Success Messages */}
              {error && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-2 p-4 rounded-lg bg-red-500/20 border border-red-500/30 text-red-200 mt-4"
                >
                  <AlertCircle className="w-5 h-5 flex-shrink-0" />
                  <span className="text-sm">{error}</span>
                </motion.div>
              )}

              {success && (
                <motion.div
                  initial={{ opacity: 0, y: -10 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="flex items-center gap-2 p-4 rounded-lg bg-green-500/20 border border-green-500/30 text-green-200 mt-4"
                >
                  <CheckCircle className="w-5 h-5 flex-shrink-0" />
                  <span className="text-sm">{success}</span>
                </motion.div>
              )}
            </Card>
          </motion.div>

          {/* Footer */}
          <motion.p
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ delay: 1.2 }}
            className="text-center text-xs text-white/30 mt-8"
          >
            Powered by AWS Cognito
          </motion.p>
        </motion.div>
      </div>
    </div>
  )
}