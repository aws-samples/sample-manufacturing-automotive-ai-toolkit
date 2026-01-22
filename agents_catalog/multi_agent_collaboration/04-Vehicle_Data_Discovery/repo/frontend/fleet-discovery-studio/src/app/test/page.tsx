"use client"

import { useState, useEffect } from "react"

export default function TestPage() {
  const [testState, setTestState] = useState("Initial")

  console.log("TestPage render, testState:", testState)

  useEffect(() => {
    console.log("TestPage useEffect running")
    setTestState("useEffect executed")

    // Simple fetch test without hooks
    async function testFetch() {
      try {
        console.log("Testing direct fetch to localhost:8000/stats/overview")
        const response = await fetch("/api/stats/overview")
        console.log("Direct fetch response:", response.status, response.ok)

        if (response.ok) {
          const data = await response.json()
          console.log("Direct fetch data:", data)
          setTestState("Fetch successful")
        } else {
          console.log("Fetch failed:", response.status)
          setTestState(`Fetch failed: ${response.status}`)
        }
      } catch (error) {
        console.error("Fetch error:", error)
        setTestState(`Fetch error: ${error}`)
      }
    }

    // Delay the fetch to see if component mounts first
    setTimeout(testFetch, 1000)
  }, [])

  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold mb-8">Minimal Test Page</h1>

      <div className="border rounded p-4">
        <h2 className="text-lg font-semibold mb-4">Component Status</h2>
        <p>Test State: <strong>{testState}</strong></p>
        <p>Component rendered at: {new Date().toISOString()}</p>
      </div>

      <div className="border rounded p-4 mt-4">
        <h2 className="text-lg font-semibold mb-4">Direct API Test</h2>
        <p>Check browser console for fetch logs...</p>
      </div>
    </div>
  )
}