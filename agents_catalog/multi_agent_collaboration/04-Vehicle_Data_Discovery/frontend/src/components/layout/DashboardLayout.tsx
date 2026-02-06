/**
 * DashboardLayout - Main Application Shell
 * 
 * Provides consistent layout with sidebar navigation, header,
 * and main content area for all dashboard pages.
 */
"use client"

import { ReactNode } from "react"
import Sidebar from "./Sidebar"
import Header from "./Header"

interface DashboardLayoutProps {
  children: ReactNode
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  return (
    <div className="min-h-screen bg-[var(--soft-grey)] font-sans selection:bg-[var(--cyber-blue)] selection:text-white">
      <Sidebar />
      <div className="pl-64 transition-all duration-300 ease-in-out">
        {/* Sticky Glass Header */}
        <div className="sticky top-0 z-50 glass-panel">
          <Header />
        </div>

        <main className="p-8 lg:p-12 max-w-[1600px] mx-auto">
          {children}
        </main>
      </div>
    </div>
  )
}