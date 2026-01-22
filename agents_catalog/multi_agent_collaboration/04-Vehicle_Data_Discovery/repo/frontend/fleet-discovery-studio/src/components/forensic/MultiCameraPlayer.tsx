"use client"

import { useState, useEffect } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Play, Pause, Volume2, VolumeX, Maximize, Camera } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"

interface MultiCameraPlayerProps {
  cameraUrls: { [key: string]: string }
  defaultCamera?: string
}

export default function MultiCameraPlayer({
  cameraUrls,
  defaultCamera = "CAM_FRONT"
}: MultiCameraPlayerProps) {
  const [activeCamera, setActiveCamera] = useState(defaultCamera)
  const [videoUrl, setVideoUrl] = useState(cameraUrls[defaultCamera] || "")
  const [isPlaying, setIsPlaying] = useState(false)
  const [isMuted, setIsMuted] = useState(false)
  const [videoElement, setVideoElement] = useState<HTMLVideoElement | null>(null)
  const [userHasSelectedCamera, setUserHasSelectedCamera] = useState(false)

  // Handle camera URL updates when active camera changes
  useEffect(() => {
    if (cameraUrls[activeCamera]) {
      setVideoUrl(cameraUrls[activeCamera])

      // Force video element to reload by clearing src first
      if (videoElement) {
        videoElement.pause()
        videoElement.currentTime = 0
        videoElement.load()  // Force reload of new source
        setIsPlaying(false)
      }
    }
  }, [activeCamera, cameraUrls, videoElement])

  // Handle defaultCamera prop changes (for URL-based auto-selection) - only if user hasn't manually selected
  useEffect(() => {
    if (!userHasSelectedCamera && defaultCamera && defaultCamera !== activeCamera && cameraUrls[defaultCamera]) {
      setActiveCamera(defaultCamera)
    }
  }, [defaultCamera, activeCamera, cameraUrls, userHasSelectedCamera])

  const handleCameraSwitch = (cameraName: string) => {
    setUserHasSelectedCamera(true)  // Mark as user-initiated selection
    setActiveCamera(cameraName)
    if (videoElement) {
      videoElement.pause()
      setIsPlaying(false)
    }
  }

  const togglePlayPause = async () => {
    if (videoElement) {
      if (isPlaying) {
        videoElement.pause()
        setIsPlaying(false)
      } else {
        try {
          // Check if video is ready to play
          if (videoElement.readyState >= HTMLMediaElement.HAVE_FUTURE_DATA) {
            await videoElement.play()
            setIsPlaying(true)
          } else {
            console.warn('Video not ready to play yet')
          }
        } catch (error) {
          console.warn('Video play failed:', error)
          // Don't update playing state if play failed
        }
      }
    }
  }

  const toggleMute = () => {
    if (videoElement) {
      videoElement.muted = !isMuted
      setIsMuted(!isMuted)
    }
  }

  const cameraDisplayNames = {
    'CAM_FRONT': 'Front',
    'CAM_BACK': 'Rear',
    'CAM_FRONT_LEFT': 'Front L',
    'CAM_FRONT_RIGHT': 'Front R',
    'CAM_BACK_LEFT': 'Rear L',
    'CAM_BACK_RIGHT': 'Rear R'
  }

  if (!cameraUrls || Object.keys(cameraUrls).length === 0) {
    return (
      <Card className="aspect-video bg-gray-900 flex items-center justify-center">
        <div className="text-center text-gray-400">
          <Camera className="w-12 h-12 mx-auto mb-4" />
          <p>No camera feeds available</p>
        </div>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      {/* Master Player */}
      <Card className="relative overflow-hidden bg-black">
        <div className="aspect-video relative">
          <AnimatePresence mode="wait">
            <motion.video
              ref={setVideoElement}
              src={videoUrl}
              controls={false}
              autoPlay={false}
              muted={isMuted}
              className="w-full h-full object-contain"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.3 }}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onLoadStart={() => setIsPlaying(false)}
            />
          </AnimatePresence>

          {/* Video Controls Overlay */}
          <div className="absolute inset-0 bg-black/20 opacity-0 hover:opacity-100 transition-opacity duration-300">
            <div className="absolute bottom-4 left-4 right-4">
              <div className="flex items-center justify-between">
                {/* Play/Pause Controls */}
                <div className="flex items-center gap-2">
                  <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={togglePlayPause}
                    className="w-10 h-10 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center hover:bg-white/30 transition-colors"
                  >
                    {isPlaying ? (
                      <Pause className="w-5 h-5 text-white" />
                    ) : (
                      <Play className="w-5 h-5 text-white ml-1" />
                    )}
                  </motion.button>

                  <motion.button
                    whileHover={{ scale: 1.1 }}
                    whileTap={{ scale: 0.9 }}
                    onClick={toggleMute}
                    className="w-8 h-8 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center hover:bg-white/30 transition-colors"
                  >
                    {isMuted ? (
                      <VolumeX className="w-4 h-4 text-white" />
                    ) : (
                      <Volume2 className="w-4 h-4 text-white" />
                    )}
                  </motion.button>
                </div>

                {/* Active Camera Label */}
                <div className="bg-[var(--cyber-blue)] text-white px-3 py-1 rounded-full text-sm font-medium">
                  {cameraDisplayNames[activeCamera as keyof typeof cameraDisplayNames] || activeCamera}
                </div>

                {/* Fullscreen */}
                <motion.button
                  whileHover={{ scale: 1.1 }}
                  whileTap={{ scale: 0.9 }}
                  className="w-8 h-8 bg-white/20 backdrop-blur-sm rounded-full flex items-center justify-center hover:bg-white/30 transition-colors"
                >
                  <Maximize className="w-4 h-4 text-white" />
                </motion.button>
              </div>
            </div>
          </div>
        </div>
      </Card>

      {/* Camera Selector Strip */}
      <div className="space-y-2">
        <h3 className="text-sm font-medium text-[var(--deep-charcoal)]">
          Camera Views ({Object.keys(cameraUrls).length})
        </h3>
        <div className="grid grid-cols-4 md:grid-cols-6 lg:grid-cols-8 gap-2">
          {Object.entries(cameraUrls).map(([cameraName, url]) => {
            const isActive = activeCamera === cameraName
            const displayName = cameraDisplayNames[cameraName as keyof typeof cameraDisplayNames] || cameraName.replace('CAM_', '')

            return (
              <motion.button
                key={cameraName}
                whileHover={{ scale: 1.05 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => handleCameraSwitch(cameraName)}
                className={`
                  relative p-3 rounded-lg text-xs font-mono transition-all duration-200
                  ${isActive
                    ? "bg-[var(--cyber-blue)] text-white ring-2 ring-[var(--cyber-blue)]/50 shadow-lg"
                    : "bg-[var(--soft-grey)] text-[var(--slate-grey)] hover:bg-gray-300"
                  }
                `}
              >
                {isActive && (
                  <motion.div
                    layoutId="activeCamera"
                    className="absolute inset-0 bg-[var(--cyber-blue)] rounded-lg"
                    initial={false}
                    transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
                  />
                )}
                <div className="relative z-10 flex flex-col items-center gap-1">
                  <Camera className="w-4 h-4" />
                  <span className="leading-tight">{displayName}</span>
                </div>
              </motion.button>
            )
          })}
        </div>
      </div>
    </div>
  )
}