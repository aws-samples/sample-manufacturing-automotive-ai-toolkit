/**
 * Sidebar - Navigation Menu
 * 
 * Vertical navigation with links to main sections: Fleet Command,
 * Analytics, Pipeline, Search, and Settings.
 */
"use client"

import Link from "next/link"
import { usePathname } from "next/navigation"
import { motion } from "framer-motion"
import {
  Grid3X3,
  Search,
  Target,
  BarChart3,
  Settings,
  Database
} from "lucide-react"

const navigation = [
  { name: "Fleet Command", href: "/", icon: Grid3X3 },
  { name: "Neural Search", href: "/search", icon: Search },
  { name: "Forensic Lens", href: "/forensic", icon: Target },
  { name: "Analytics", href: "/analytics", icon: BarChart3 },
  { name: "Data Pipeline", href: "/pipeline", icon: Database },
  { name: "Settings", href: "/settings", icon: Settings },
]

export default function Sidebar() {
  const pathname = usePathname()

  return (
    <div className="bg-[var(--pure-white)] border-r border-gray-200 w-64 h-screen fixed left-0 top-0 z-50">
      {/* Logo/Brand */}
      <div className="p-6 border-b border-gray-200">
        <h1 className="text-xl font-semibold text-[var(--deep-charcoal)] tracking-tight">
          Fleet Discovery
        </h1>
        <p className="text-xs text-[var(--slate-grey)] mt-1">
          Engineering Laboratory
        </p>
      </div>

      {/* Navigation */}
      <nav className="mt-8 px-4">
        <ul className="space-y-2">
          {navigation.map((item) => {
            const isActive = pathname === item.href
            const Icon = item.icon

            return (
              <li key={item.name}>
                <Link
                  href={item.href}
                  className={`relative flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-all duration-200 group ${
                    isActive
                      ? "bg-[var(--cyber-blue)] text-white"
                      : "text-[var(--deep-charcoal)] hover:bg-[var(--soft-grey)]"
                  }`}
                >
                  {isActive && (
                    <motion.div
                      layoutId="activeTab"
                      className="absolute inset-0 bg-[var(--cyber-blue)] rounded-lg"
                      initial={false}
                      transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                    />
                  )}
                  <Icon
                    className={`w-4 h-4 z-10 ${
                      isActive ? "text-white" : "text-[var(--slate-grey)]"
                    }`}
                  />
                  <span className="z-10">{item.name}</span>
                </Link>
              </li>
            )
          })}
        </ul>
      </nav>

      {/* Status Indicator */}
      <div className="absolute bottom-6 left-4 right-4">
        <div className="bg-[var(--soft-grey)] rounded-lg p-3">
          <div className="flex items-center gap-2 mb-1">
            <div className="w-2 h-2 bg-[var(--success-green)] rounded-full"></div>
            <span className="text-xs font-medium text-[var(--deep-charcoal)]">
              Pipeline Active
            </span>
          </div>
          <p className="text-xs text-[var(--slate-grey)]">
            Processing 24/7
          </p>
        </div>
      </div>
    </div>
  )
}