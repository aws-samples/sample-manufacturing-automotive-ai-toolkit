"use client"

import { useState, useCallback, useRef } from "react"
import { motion, AnimatePresence } from "framer-motion"
import { Upload, CheckCircle, AlertCircle, X, FileText, Loader2, Database } from "lucide-react"
import { Card } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"

interface DataFormat {
  id: string
  name: string
  description: string
  extensions: string[]
  maxSize: string
  supported: boolean
}

interface UploadState {
  file: File | null
  status: 'idle' | 'uploading' | 'success' | 'error'
  progress: number
  error?: string
  sceneId?: string
  selectedFormat: string
}

export default function RosBagUpload() {
  // Data format definitions - your colleague's extensibility framework
  const dataFormats: DataFormat[] = [
    {
      id: 'fleet_ros',
      name: 'ROS Bags',
      description: 'ROS bag files (.bag) and SQLite format (.db3) with multi-sensor data',
      extensions: ['.bag', '.db3'],
      maxSize: '5GB',
      supported: true
    },
    {
      id: 'nvidia_physicalai',
      name: 'NVIDIA PhysicalAI',
      description: '1,727 hours across 25 countries - Multi-sensor AV data',
      extensions: ['.zip', '.tar'],
      maxSize: '10GB',
      supported: false // Framework ready, extractor not built yet
    },
    {
      id: 'ros2_mcap',
      name: 'ROS2 MCAP',
      description: 'Modern ROS2 message capture files',
      extensions: ['.mcap'],
      maxSize: '5GB',
      supported: false
    },
    {
      id: 'vector_mdf4',
      name: 'Vector MDF4',
      description: 'CANape measurement files with CAN/LIN data',
      extensions: ['.mf4', '.mdf'],
      maxSize: '2GB',
      supported: false
    },
    {
      id: 'direct_video',
      name: 'Direct MP4 Videos',
      description: 'Raw multi-camera MP4 files (skip Phase 1-2)',
      extensions: ['.mp4', '.avi'],
      maxSize: '8GB',
      supported: false
    }
  ]

  const [uploadState, setUploadState] = useState<UploadState>({
    file: null,
    status: 'idle',
    progress: 0,
    selectedFormat: 'fleet_ros' // Default to Fleet ROS
  })
  const [isDragOver, setIsDragOver] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    setIsDragOver(false)

    const files = Array.from(e.dataTransfer.files)
    const selectedFormatConfig = dataFormats.find(f => f.id === uploadState.selectedFormat)

    if (!selectedFormatConfig) return

    const validFile = files.find(file => {
      const extension = '.' + file.name.split('.').pop()?.toLowerCase()
      return selectedFormatConfig.extensions.includes(extension)
    })

    if (validFile) {
      setUploadState(prev => ({
        ...prev,
        file: validFile,
        status: 'idle',
        progress: 0,
        error: undefined // Clear any previous errors
      }))
    } else {
      // Show user-friendly error message for drag-and-drop
      const droppedExtension = files[0] ? '.' + files[0].name.split('.').pop()?.toLowerCase() : 'unknown'
      setUploadState(prev => ({
        ...prev,
        status: 'error',
        error: `Invalid file format. ${selectedFormatConfig?.name} expects ${selectedFormatConfig?.extensions.join(', ')} files, but you dropped ${droppedExtension}.`
      }))
      console.warn(`File format not supported for ${selectedFormatConfig.name}. Expected: ${selectedFormatConfig.extensions.join(', ')}`)
    }
  }, [uploadState.selectedFormat, dataFormats])

  const handleFileSelect = (file: File) => {
    const selectedFormatConfig = dataFormats.find(f => f.id === uploadState.selectedFormat)
    const extension = '.' + file.name.split('.').pop()?.toLowerCase()

    if (selectedFormatConfig?.extensions.includes(extension)) {
      setUploadState(prev => ({
        ...prev,
        file: file,
        status: 'idle',
        progress: 0,
        error: undefined // Clear any previous errors
      }))
    } else {
      // Show user-friendly error message
      setUploadState(prev => ({
        ...prev,
        status: 'error',
        error: `Invalid file format. ${selectedFormatConfig?.name} expects ${selectedFormatConfig?.extensions.join(', ')} files, but you selected ${extension}.`
      }))
      console.warn(`File format not supported for ${selectedFormatConfig?.name}. Expected: ${selectedFormatConfig?.extensions.join(', ')}`)
    }
  }

  const uploadToS3 = async (presignedData: any, file: File) => {
    // Fix: Use regional S3 endpoint for CORS compatibility
    let uploadUrl = presignedData.url
    if (uploadUrl.includes('.s3.amazonaws.com')) {
      uploadUrl = uploadUrl.replace('.s3.amazonaws.com', '.s3.us-west-2.amazonaws.com')
    }
    console.log('Starting S3 upload to:', uploadUrl)

    const formData = new FormData()

    // Add all the required fields for S3 upload
    Object.keys(presignedData.fields).forEach(key => {
      formData.append(key, presignedData.fields[key])
      console.log('📝 Added field:', key, '=', presignedData.fields[key])
    })

    // Add the file last
    formData.append('file', file)
    console.log('📁 Added file:', file.name, 'size:', file.size)

    const xhr = new XMLHttpRequest()

    return new Promise<void>((resolve, reject) => {
      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          const progress = Math.round((event.loaded / event.total) * 100)
          console.log('Upload progress:', progress + '%')
          setUploadState(prev => ({ ...prev, progress }))
        }
      })

      xhr.addEventListener('load', () => {
        console.log('Upload completed with status:', xhr.status)
        console.log('📄 Response text:', xhr.responseText)
        if (xhr.status === 204) {
          resolve()
        } else {
          reject(new Error(`Upload failed with status ${xhr.status}: ${xhr.responseText}`))
        }
      })

      xhr.addEventListener('error', (event) => {
        console.error('Upload XHR error:', event)
        console.error(' XHR status:', xhr.status)
        console.error(' XHR response:', xhr.responseText)
        reject(new Error(`Upload failed - XHR error. Status: ${xhr.status}, Response: ${xhr.responseText}`))
      })

      console.log(' Opening POST request to:', uploadUrl)
      xhr.open('POST', uploadUrl)
      xhr.send(formData)
    })
  }

  const handleUpload = async () => {
    if (!uploadState.file) return

    setUploadState(prev => ({ ...prev, status: 'uploading', progress: 0 }))

    try {
      // Step 1: Get presigned URL from your local backend with format metadata
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || '/api'
      const selectedFormat = dataFormats.find(f => f.id === uploadState.selectedFormat)

      console.log(' Requesting upload authorization from:', apiUrl)
      console.log(' Selected format:', selectedFormat?.name, '(', uploadState.selectedFormat, ')')

      const authResponse = await fetch(
        `${apiUrl}/upload/authorize?filename=${encodeURIComponent(uploadState.file.name)}&file_type=application/octet-stream&data_format=${uploadState.selectedFormat}&format_name=${encodeURIComponent(selectedFormat?.name || '')}`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
          }
        }
      )

      console.log(' Authorization response status:', authResponse.status)

      if (!authResponse.ok) {
        const errorText = await authResponse.text()
        console.error(' Authorization failed:', errorText)
        throw new Error(`Failed to get upload authorization: ${authResponse.status} - ${errorText}`)
      }

      const presignedData = await authResponse.json()
      console.log('Got presigned data:', { url: presignedData.url, fields: Object.keys(presignedData.fields || {}) })

      // Step 2: Upload directly to S3
      await uploadToS3(presignedData, uploadState.file)

      // Step 3: Extract scene ID from filename or generate one
      const sceneId = uploadState.file.name.replace(/\.(bag|db3)$/, '') || 'uploaded-scene'

      setUploadState(prev => ({
        ...prev,
        status: 'success',
        progress: 100,
        sceneId: sceneId
      }))

    } catch (error) {
      console.error('Upload error:', error)
      setUploadState(prev => ({
        ...prev,
        status: 'error',
        error: error instanceof Error ? error.message : 'Upload failed'
      }))
    }
  }

  const resetUpload = () => {
    setUploadState(prev => ({
      ...prev,
      file: null,
      status: 'idle',
      progress: 0,
      error: undefined,
      sceneId: undefined
    }))
    if (fileInputRef.current) {
      fileInputRef.current.value = ''
    }
  }

  const formatFileSize = (bytes: number) => {
    if (bytes === 0) return '0 Bytes'
    const k = 1024
    const sizes = ['Bytes', 'KB', 'MB', 'GB']
    const i = Math.floor(Math.log(bytes) / Math.log(k))
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{
        duration: 0.4,
        type: "spring",
        stiffness: 100
      }}
    >
      <Card className="overflow-hidden border-0 shadow-[var(--shadow-card)] hover:shadow-[var(--shadow-card-hover)] transition-all duration-500 bg-white rounded-2xl">
        <div className="p-8">
          {/* Header */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            className="space-y-6 mb-8"
          >
            <div className="flex items-center gap-4">
              <div className="w-12 h-12 bg-gradient-to-br from-[var(--cyber-blue)] to-[var(--cyber-blue)]/80 rounded-2xl flex items-center justify-center shadow-lg shadow-[var(--cyber-blue)]/20">
                <Database className="w-6 h-6 text-white" />
              </div>
              <div>
                <h3 className="text-xl font-semibold text-[var(--deep-charcoal)] tracking-tight">
                  Upload Autonomous Vehicle Data
                </h3>
                <p className="text-[var(--slate-grey)] text-sm mt-1">
                  Trigger 6-phase AI processing pipeline for behavioral analysis
                </p>
              </div>
            </div>

            {/* Format Selection - Your Colleague's Extensibility Framework */}
            <div className="bg-gradient-to-r from-[var(--soft-grey)] to-white rounded-xl p-4 border border-gray-100">
              <label className="block text-sm font-medium text-[var(--deep-charcoal)] mb-3">
                📊 Select Data Format
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                {dataFormats.map((format) => (
                  <motion.div
                    key={format.id}
                    initial={{ opacity: 0, scale: 0.95 }}
                    animate={{ opacity: 1, scale: 1 }}
                    transition={{ delay: 0.1 }}
                    className={`relative cursor-pointer rounded-lg border-2 p-3 transition-all duration-200 ${
                      uploadState.selectedFormat === format.id
                        ? 'border-[var(--cyber-blue)] bg-[var(--cyber-blue)]/5 shadow-sm'
                        : 'border-gray-200 hover:border-[var(--cyber-blue)]/40 hover:bg-white'
                    } ${!format.supported ? 'opacity-60' : ''}`}
                    onClick={() => {
                      if (format.supported) {
                        setUploadState(prev => ({ ...prev, selectedFormat: format.id }))
                      }
                    }}
                  >
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2">
                          <h4 className="font-medium text-[var(--deep-charcoal)] text-sm">
                            {format.name}
                          </h4>
                          {format.supported ? (
                            <Badge className="bg-[var(--success-green)] text-white text-xs px-2 py-0.5">
                              Supported
                            </Badge>
                          ) : (
                            <Badge className="bg-[var(--slate-grey)] text-white text-xs px-2 py-0.5">
                              Coming Soon
                            </Badge>
                          )}
                        </div>
                        <p className="text-xs text-[var(--slate-grey)] mt-1 leading-relaxed">
                          {format.description}
                        </p>
                        <div className="flex items-center gap-2 mt-2">
                          <span className="text-xs text-[var(--cyber-blue)] font-medium">
                            {format.extensions.join(', ')}
                          </span>
                          <span className="text-xs text-[var(--slate-grey)]">
                            Max {format.maxSize}
                          </span>
                        </div>
                      </div>
                      {uploadState.selectedFormat === format.id && (
                        <div className="w-4 h-4 bg-[var(--cyber-blue)] rounded-full flex items-center justify-center">
                          <CheckCircle className="w-3 h-3 text-white" />
                        </div>
                      )}
                    </div>
                  </motion.div>
                ))}
              </div>
              {uploadState.selectedFormat !== 'fleet_ros' && (
                <div className="mt-3 p-3 bg-orange-50 border border-orange-200 rounded-lg">
                  <p className="text-xs text-orange-600">
                    🚧 <strong>Framework Ready:</strong> This format is configured but the extractor is not built yet.
                    Contact your team to build the {dataFormats.find(f => f.id === uploadState.selectedFormat)?.name} extractor for production use.
                  </p>
                </div>
              )}
            </div>
          </motion.div>

          <AnimatePresence mode="wait">
            {uploadState.status === 'idle' && !uploadState.file && (
              <motion.div
                key="dropzone"
                initial={{ opacity: 0, scale: 0.95 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.95 }}
                transition={{ duration: 0.3 }}
                className={`
                  relative border-2 border-dashed rounded-2xl p-12 text-center transition-all duration-300 group cursor-pointer
                  ${isDragOver
                    ? 'border-[var(--cyber-blue)] bg-gradient-to-b from-[var(--cyber-blue)]/5 to-[var(--cyber-blue)]/10 shadow-inner'
                    : 'border-gray-200 hover:border-[var(--cyber-blue)]/60 hover:bg-gradient-to-b hover:from-[var(--soft-grey)] hover:to-white'
                  }
                `}
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => fileInputRef.current?.click()}
              >
                <motion.div
                  animate={isDragOver ? { scale: 1.1, y: -5 } : { scale: 1, y: 0 }}
                  transition={{ duration: 0.2 }}
                  className="flex flex-col items-center"
                >
                  <div className={`
                    w-16 h-16 rounded-2xl flex items-center justify-center mb-6 transition-all duration-300
                    ${isDragOver
                      ? 'bg-[var(--cyber-blue)] shadow-lg shadow-[var(--cyber-blue)]/30'
                      : 'bg-[var(--soft-grey)] group-hover:bg-[var(--cyber-blue)]/10'
                    }
                  `}>
                    <Upload className={`w-8 h-8 transition-colors duration-300 ${
                      isDragOver ? 'text-white' : 'text-[var(--slate-grey)] group-hover:text-[var(--cyber-blue)]'
                    }`} />
                  </div>

                  <h4 className="text-xl font-semibold text-[var(--deep-charcoal)] mb-3">
                    {isDragOver ? 'Release to upload' : `Drag and drop your ${dataFormats.find(f => f.id === uploadState.selectedFormat)?.name || 'data'} file`}
                  </h4>

                  <p className="text-[var(--slate-grey)] mb-6 leading-relaxed">
                    Support for {dataFormats.find(f => f.id === uploadState.selectedFormat)?.extensions.join(', ')} files up to {dataFormats.find(f => f.id === uploadState.selectedFormat)?.maxSize}<br />
                    <span className="text-sm">Automatic pipeline trigger • Multi-camera analysis • HIL qualification</span>
                  </p>

                  <Button
                    variant="outline"
                    className="bg-white border-2 border-[var(--cyber-blue)]/20 text-[var(--cyber-blue)] hover:bg-[var(--cyber-blue)] hover:text-white hover:border-[var(--cyber-blue)] transition-all duration-300 px-6 py-3 rounded-xl shadow-sm"
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Browse Files
                  </Button>
                </motion.div>

                <input
                  ref={fileInputRef}
                  type="file"
                  accept={dataFormats.find(f => f.id === uploadState.selectedFormat)?.extensions.join(',') || '.bag,.db3'}
                  className="hidden"
                  onChange={(e) => {
                    const file = e.target.files?.[0]
                    if (file) handleFileSelect(file)
                  }}
                />
              </motion.div>
            )}

            {uploadState.file && uploadState.status === 'idle' && (
              <motion.div
                key="file-selected"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.4, type: "spring", stiffness: 100 }}
                className="space-y-6"
              >
                <div className="flex items-center justify-between p-6 bg-gradient-to-r from-[var(--soft-grey)] to-white rounded-2xl border border-gray-100">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 bg-[var(--cyber-blue)]/10 rounded-xl flex items-center justify-center">
                      <FileText className="w-6 h-6 text-[var(--cyber-blue)]" />
                    </div>
                    <div>
                      <p className="font-semibold text-[var(--deep-charcoal)] text-lg">
                        {uploadState.file.name}
                      </p>
                      <p className="text-[var(--slate-grey)] text-sm">
                        {formatFileSize(uploadState.file.size)} • Ready for processing
                      </p>
                    </div>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={resetUpload}
                    className="bg-white border-gray-200 hover:bg-red-50 hover:border-red-200 hover:text-red-600 rounded-lg"
                  >
                    <X className="w-4 h-4" />
                  </Button>
                </div>

                <div className="flex gap-4">
                  <Button
                    onClick={handleUpload}
                    className="flex-1 bg-gradient-to-r from-[var(--cyber-blue)] to-[var(--cyber-blue)]/90 hover:from-[var(--cyber-blue)]/90 hover:to-[var(--cyber-blue)]/80 text-white py-4 rounded-xl shadow-lg shadow-[var(--cyber-blue)]/20 transition-all duration-300"
                  >
                    <Database className="w-5 h-5 mr-3" />
                    Upload & Process
                  </Button>
                  <Button
                    variant="outline"
                    onClick={resetUpload}
                    className="bg-white border-gray-200 text-[var(--slate-grey)] hover:bg-[var(--soft-grey)] py-4 px-6 rounded-xl"
                  >
                    Cancel
                  </Button>
                </div>
              </motion.div>
            )}

            {uploadState.status === 'uploading' && (
              <motion.div
                key="uploading"
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -20 }}
                transition={{ duration: 0.4, type: "spring", stiffness: 100 }}
                className="space-y-6"
              >
                <div className="flex items-center gap-4 mb-6">
                  <div className="w-12 h-12 bg-gradient-to-br from-[var(--cyber-blue)] to-[var(--cyber-blue)]/80 rounded-2xl flex items-center justify-center shadow-lg shadow-[var(--cyber-blue)]/30">
                    <Loader2 className="w-6 h-6 text-white animate-spin" />
                  </div>
                  <div>
                    <p className="font-semibold text-[var(--deep-charcoal)] text-lg">
                      Uploading {uploadState.file?.name}
                    </p>
                    <p className="text-[var(--slate-grey)]">
                      {uploadState.progress}% complete • Preparing for pipeline processing
                    </p>
                  </div>
                </div>

                <div className="space-y-3">
                  <div className="flex justify-between text-sm">
                    <span className="text-[var(--slate-grey)]">Upload Progress</span>
                    <span className="font-medium text-[var(--cyber-blue)]">{uploadState.progress}%</span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
                    <motion.div
                      className="bg-gradient-to-r from-[var(--cyber-blue)] to-[var(--cyber-blue)]/80 h-full rounded-full shadow-sm"
                      initial={{ width: 0 }}
                      animate={{ width: `${uploadState.progress}%` }}
                      transition={{ duration: 0.5, ease: "easeOut" }}
                    />
                  </div>
                </div>
              </motion.div>
            )}

            {uploadState.status === 'success' && (
              <motion.div
                key="success"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.5, type: "spring", stiffness: 100 }}
                className="text-center py-8"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
                  className="w-20 h-20 bg-gradient-to-br from-[var(--success-green)] to-[var(--success-green)]/80 rounded-full flex items-center justify-center mx-auto mb-6 shadow-lg shadow-[var(--success-green)]/20"
                >
                  <CheckCircle className="w-10 h-10 text-white" />
                </motion.div>

                <h4 className="text-2xl font-semibold text-[var(--deep-charcoal)] mb-3">
                  Upload Successful!
                </h4>
                <p className="text-[var(--slate-grey)] mb-6 leading-relaxed">
                  Your Fleet ROS bag file has been uploaded to S3.<br />
                  <span className="font-medium text-[var(--cyber-blue)]">6-phase processing pipeline will begin shortly.</span>
                </p>

                <div className="flex justify-center gap-3 mb-6">
                  <Badge className="bg-gradient-to-r from-[var(--success-green)] to-[var(--success-green)]/80 text-white px-4 py-2 rounded-lg shadow-sm">
                    📁 {uploadState.file?.name?.slice(0, 20)}...
                  </Badge>
                  <Badge className="bg-gradient-to-r from-[var(--cyber-blue)] to-[var(--cyber-blue)]/80 text-white px-4 py-2 rounded-lg shadow-sm">
                    🎯 {uploadState.sceneId}
                  </Badge>
                </div>

                <Button
                  onClick={resetUpload}
                  variant="outline"
                  className="bg-white border-2 border-[var(--cyber-blue)]/20 text-[var(--cyber-blue)] hover:bg-[var(--cyber-blue)] hover:text-white hover:border-[var(--cyber-blue)] px-6 py-3 rounded-xl transition-all duration-300"
                >
                  <Upload className="w-4 h-4 mr-2" />
                  Upload Another File
                </Button>
              </motion.div>
            )}

            {uploadState.status === 'error' && (
              <motion.div
                key="error"
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.9 }}
                transition={{ duration: 0.5, type: "spring", stiffness: 100 }}
                className="text-center py-8"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ delay: 0.2, type: "spring", stiffness: 200 }}
                  className="w-20 h-20 bg-gradient-to-br from-[var(--safety-orange)] to-[var(--safety-orange)]/80 rounded-full flex items-center justify-center mx-auto mb-6 shadow-lg shadow-[var(--safety-orange)]/20"
                >
                  <AlertCircle className="w-10 h-10 text-white" />
                </motion.div>

                <h4 className="text-2xl font-semibold text-[var(--deep-charcoal)] mb-3">
                  Upload Failed
                </h4>
                <p className="text-[var(--slate-grey)] mb-6">
                  {uploadState.error || 'An unexpected error occurred during upload'}
                </p>

                <div className="flex justify-center gap-4">
                  <Button
                    onClick={handleUpload}
                    className="bg-gradient-to-r from-[var(--cyber-blue)] to-[var(--cyber-blue)]/90 hover:from-[var(--cyber-blue)]/90 hover:to-[var(--cyber-blue)]/80 text-white px-6 py-3 rounded-xl shadow-lg shadow-[var(--cyber-blue)]/20"
                  >
                    <Upload className="w-4 h-4 mr-2" />
                    Try Again
                  </Button>
                  <Button
                    onClick={resetUpload}
                    variant="outline"
                    className="bg-white border-gray-200 text-[var(--slate-grey)] hover:bg-[var(--soft-grey)] px-6 py-3 rounded-xl"
                  >
                    Choose Different File
                  </Button>
                </div>
              </motion.div>
            )}
          </AnimatePresence>
        </div>
      </Card>
    </motion.div>
  )
}