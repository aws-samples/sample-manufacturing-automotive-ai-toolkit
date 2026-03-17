/**
 * Header - Top Navigation Bar
 * 
 * Application header with branding, user menu, and sign-out button.
 * Displays current user info from auth context.
 */
"use client"

import { useState } from "react"
import { motion } from "framer-motion"
import { Bell, User, Activity, Clock, LogOut, ChevronDown } from "lucide-react"
import { Badge } from "@/components/ui/badge"
import { useAuthContext } from "@/components/auth/AuthProvider"

export default function Header() {
  const { user, signOut } = useAuthContext()
  const [showUserMenu, setShowUserMenu] = useState(false)

  return (
    <header className="bg-[var(--pure-white)] border-b border-gray-200 h-16 flex items-center justify-between px-6 ml-64">
      {/* Left - System Status */}
      <div className="flex items-center gap-6">
        <div className="flex items-center gap-2">
          <Activity className="w-4 h-4 text-[var(--success-green)]" />
          <span className="text-sm font-medium text-[var(--deep-charcoal)]">
            System Healthy
          </span>
        </div>

        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-[var(--slate-grey)]" />
          <span className="text-sm text-[var(--slate-grey)]">
            Last sync: 2 min ago
          </span>
        </div>
      </div>

      {/* Right - User Controls */}
      <div className="flex items-center gap-4">
        {/* Notifications */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          className="relative p-2 rounded-lg hover:bg-[var(--soft-grey)] transition-colors"
        >
          <Bell className="w-5 h-5 text-[var(--slate-grey)]" />
          <Badge
            variant="destructive"
            className="absolute -top-1 -right-1 w-4 h-4 p-0 text-xs flex items-center justify-center bg-[var(--safety-orange)] border-0"
          >
            3
          </Badge>
        </motion.button>

        {/* User Profile Dropdown */}
        <div className="relative">
          <motion.button
            whileHover={{ scale: 1.02 }}
            onClick={() => setShowUserMenu(!showUserMenu)}
            className="flex items-center gap-2 p-2 rounded-lg hover:bg-[var(--soft-grey)] transition-colors"
          >
            <div className="w-8 h-8 bg-gradient-to-r from-[var(--cyber-blue)] to-purple-500 rounded-full flex items-center justify-center">
              <User className="w-4 h-4 text-white" />
            </div>
            <div className="text-left">
              <p className="text-sm font-medium text-[var(--deep-charcoal)]">
                {user?.email?.split('@')[0] || 'Fleet Engineer'}
              </p>
              <p className="text-xs text-[var(--slate-grey)]">
                Fleet Discovery Team
              </p>
            </div>
            <ChevronDown className={`w-4 h-4 text-[var(--slate-grey)] transition-transform ${showUserMenu ? 'rotate-180' : ''}`} />
          </motion.button>

          {/* User Dropdown Menu */}
          {showUserMenu && (
            <motion.div
              initial={{ opacity: 0, y: -10 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -10 }}
              className="absolute right-0 top-full mt-2 w-56 bg-white rounded-xl shadow-lg border border-gray-200 py-2 z-50"
            >
              {/* User Info Section */}
              <div className="px-4 py-3 border-b border-gray-100">
                <p className="text-sm font-medium text-[var(--deep-charcoal)]">
                  {user?.email || 'engineer@example.com'}
                </p>
                <p className="text-xs text-[var(--slate-grey)] mt-1">
                  Fleet Discovery Platform
                </p>
              </div>

              {/* Sign Out Button */}
              <button
                onClick={signOut}
                className="w-full px-4 py-2 text-left text-sm text-red-600 hover:bg-red-50 transition-colors flex items-center gap-2"
              >
                <LogOut className="w-4 h-4" />
                Sign Out
              </button>
            </motion.div>
          )}
        </div>
      </div>
    </header>
  )
}