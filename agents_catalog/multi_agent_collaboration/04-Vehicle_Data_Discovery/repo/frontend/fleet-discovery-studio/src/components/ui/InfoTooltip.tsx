"use client"

import { useState, useRef, useEffect } from "react"
import { createPortal } from "react-dom"
import { motion, AnimatePresence } from "framer-motion"
import { Info } from "lucide-react"

interface InfoTooltipProps {
  title: string
  description: string
  calculation?: string
  position?: 'top' | 'bottom' | 'left' | 'right' | 'auto'
  size?: 'sm' | 'md' | 'lg'
}

export default function InfoTooltip({
  title,
  description,
  calculation,
  position = 'auto',
  size = 'md'
}: InfoTooltipProps) {
  const [isHovered, setIsHovered] = useState(false)
  const [smartPosition, setSmartPosition] = useState<'top' | 'bottom' | 'left' | 'right'>('top')
  const [triggerRect, setTriggerRect] = useState<DOMRect | null>(null)
  const [mounted, setMounted] = useState(false)
  const triggerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setMounted(true)
  }, [])

  const sizeClasses = {
    sm: 'w-3.5 h-3.5',
    md: 'w-4 h-4',
    lg: 'w-5 h-5'
  }

  const iconSizeClasses = {
    sm: 'w-2.5 h-2.5',
    md: 'w-3 h-3',
    lg: 'w-3.5 h-3.5'
  }

  // Calculate fixed position coordinates for portal rendering
  const getFixedPosition = () => {
    if (!triggerRect) return { top: 0, left: 0 }

    const tooltipWidth = 280
    const tooltipHeight = 150
    const margin = 12

    let top = 0
    let left = 0

    switch (smartPosition) {
      case 'top':
        top = triggerRect.top - tooltipHeight - margin
        left = triggerRect.left + triggerRect.width / 2 - tooltipWidth / 2
        break
      case 'bottom':
        top = triggerRect.bottom + margin
        left = triggerRect.left + triggerRect.width / 2 - tooltipWidth / 2
        break
      case 'left':
        top = triggerRect.top + triggerRect.height / 2 - tooltipHeight / 2
        left = triggerRect.left - tooltipWidth - margin
        break
      case 'right':
        top = triggerRect.top + triggerRect.height / 2 - tooltipHeight / 2
        left = triggerRect.right + margin
        break
    }

    // Ensure tooltip stays within viewport bounds
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight

    top = Math.max(margin, Math.min(top, viewportHeight - tooltipHeight - margin))
    left = Math.max(margin, Math.min(left, viewportWidth - tooltipWidth - margin))

    return { top, left }
  }

  const arrowPositions = {
    top: 'top-full left-1/2 -translate-x-1/2 border-l-transparent border-r-transparent border-b-transparent',
    bottom: 'bottom-full left-1/2 -translate-x-1/2 border-l-transparent border-r-transparent border-t-transparent',
    left: 'left-full top-1/2 -translate-y-1/2 border-t-transparent border-b-transparent border-r-transparent',
    right: 'right-full top-1/2 -translate-y-1/2 border-t-transparent border-b-transparent border-l-transparent'
  }

  // Enhanced smart positioning with container escape logic
  const calculateBestPosition = () => {
    if (position !== 'auto') {
      setSmartPosition(position)
      return
    }

    if (!triggerRef.current) return

    const rect = triggerRef.current.getBoundingClientRect()
    setTriggerRect(rect) // Store for fixed positioning
    const viewportWidth = window.innerWidth
    const viewportHeight = window.innerHeight
    const tooltipWidth = 280 // Approximate tooltip width
    const tooltipHeight = 150 // Approximate tooltip height
    const margin = 20 // Safety margin

    // Check available space in each direction from trigger element
    const spaceTop = rect.top
    const spaceBottom = viewportHeight - rect.bottom
    const spaceLeft = rect.left
    const spaceRight = viewportWidth - rect.right

    console.log(' HIL Tooltip Positioning Debug:', {
      triggerRect: rect,
      spaces: { spaceTop, spaceBottom, spaceLeft, spaceRight },
      viewport: { viewportWidth, viewportHeight },
      tooltipSize: { tooltipWidth, tooltipHeight }
    })

    // Enhanced priority logic for container-trapped elements
    // For elements in top-right corner, prefer left or bottom positioning
    const isTopRightCorner = rect.top < 100 && rect.right > viewportWidth - 200

    if (isTopRightCorner) {
      console.log('Detected top-right corner element, using special positioning')
      // For top-right elements, prefer left > bottom > top > right
      if (spaceLeft >= tooltipWidth + margin) {
        setSmartPosition('left')
      } else if (spaceBottom >= tooltipHeight + margin) {
        setSmartPosition('bottom')
      } else if (spaceTop >= tooltipHeight + margin) {
        setSmartPosition('top')
      } else {
        setSmartPosition('right') // Fallback
      }
    } else {
      // Normal priority: bottom > top > right > left
      if (spaceBottom >= tooltipHeight + margin) {
        setSmartPosition('bottom')
      } else if (spaceTop >= tooltipHeight + margin) {
        setSmartPosition('top')
      } else if (spaceRight >= tooltipWidth + margin) {
        setSmartPosition('right')
      } else if (spaceLeft >= tooltipWidth + margin) {
        setSmartPosition('left')
      } else {
        // Fallback: choose the direction with most space
        const maxSpace = Math.max(spaceTop, spaceBottom, spaceLeft, spaceRight)
        if (maxSpace === spaceBottom) setSmartPosition('bottom')
        else if (maxSpace === spaceTop) setSmartPosition('top')
        else if (maxSpace === spaceRight) setSmartPosition('right')
        else setSmartPosition('left')
      }
    }

    console.log('Selected position:', smartPosition)
  }

  useEffect(() => {
    if (isHovered) {
      calculateBestPosition()
    }
  }, [isHovered, position])

  return (
    <div className="relative inline-flex">
      <motion.div
        ref={triggerRef}
        className={`
          inline-flex items-center justify-center rounded-full cursor-help transition-all duration-300
          bg-[var(--soft-grey)] hover:bg-[var(--cyber-blue)]/10
          border border-gray-200 hover:border-[var(--cyber-blue)]/30
          ${sizeClasses[size]}
        `}
        onHoverStart={() => setIsHovered(true)}
        onHoverEnd={() => setIsHovered(false)}
        whileHover={{ scale: 1.05 }}
        whileTap={{ scale: 0.95 }}
        transition={{ duration: 0.2, ease: "easeOut" }}
      >
        <Info
          className={`${iconSizeClasses[size]} text-[var(--slate-grey)] hover:text-[var(--cyber-blue)] transition-colors duration-300`}
          strokeWidth={2}
        />
      </motion.div>

      {/* Portal-rendered tooltip to escape container boundaries */}
      {mounted && isHovered && triggerRect && createPortal(
        <AnimatePresence>
          <motion.div
            initial={{
              opacity: 0,
              scale: 0.8,
            }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{
              opacity: 0,
              scale: 0.8,
            }}
            transition={{
              duration: 0.25,
              ease: [0.16, 1, 0.3, 1], // Apple's spring curve
              scale: { duration: 0.2 }
            }}
            className="fixed z-50 bg-[var(--pure-white)] rounded-2xl shadow-[var(--shadow-card-hover)] px-4 py-3 max-w-xs w-max min-w-64 border border-gray-100 backdrop-blur-xl"
            style={{
              ...getFixedPosition(),
              boxShadow: '0 25px 50px -12px rgba(0, 0, 0, 0.15), 0 0 0 1px rgba(0, 0, 0, 0.05)',
            }}
          >
            {/* Subtle Arrow */}
            <div
              className={`absolute w-0 h-0 border-6 ${arrowPositions[smartPosition]}`}
              style={{
                borderTopColor: smartPosition === 'bottom' ? 'white' : 'transparent',
                borderBottomColor: smartPosition === 'top' ? 'white' : 'transparent',
                borderLeftColor: smartPosition === 'right' ? 'white' : 'transparent',
                borderRightColor: smartPosition === 'left' ? 'white' : 'transparent',
              }}
            />

            {/* Content with Apple-grade typography */}
            <div className="space-y-3">
              <h4 className="font-semibold text-sm text-[var(--deep-charcoal)] tracking-tight">
                {title}
              </h4>
              <p className="text-xs text-[var(--slate-grey)] leading-relaxed">
                {description}
              </p>
              {calculation && (
                <div className="pt-3 border-t border-[var(--soft-grey)]">
                  <div className="flex items-center gap-1.5 mb-2">
                    <div className="w-1.5 h-1.5 bg-[var(--cyber-blue)] rounded-full"></div>
                    <p className="text-xs text-[var(--cyber-blue)] font-medium tracking-tight">
                      Calculation Method
                    </p>
                  </div>
                  <p className="text-xs text-[var(--slate-grey)] leading-relaxed pl-3 font-mono bg-[var(--soft-grey)] rounded-lg p-2">
                    {calculation}
                  </p>
                </div>
              )}
            </div>
          </motion.div>
        </AnimatePresence>,
        document.body
      )}
    </div>
  )
}