/**
 * Forensic Page - Scene Detail View
 * 
 * Displays detailed analysis of a single driving scene including
 * multi-camera video playback, agent analysis results, and metrics.
 * 
 * @route /forensic?scene={sceneId}
 */
'use client';

import React, { Suspense } from 'react';
import { useSearchParams } from 'next/navigation';
import DashboardLayout from "@/components/layout/DashboardLayout";
import ClientForensicContent from "@/components/forensic/ClientForensicContent";
import ProtectedRoute from "@/components/auth/ProtectedRoute";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowLeft } from "lucide-react";

// Content component that uses the searchParams hook
function ForensicContent() {
  const searchParams = useSearchParams();
  const sceneId = searchParams.get('id'); // Reads ?id=scene-0048
  const initialCamera = searchParams.get('camera'); // Reads ?camera=CAM_LEFT (NEW)

  if (!sceneId) {
    return (
      <DashboardLayout>
        <div className="text-center py-16">
          <div className="text-gray-500 mb-6">
            <svg className="w-16 h-16 mx-auto" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
          </div>
          <h2 className="text-2xl font-semibold text-gray-800 mb-3">No Scene Selected</h2>
          <p className="text-gray-600 mb-6">
            Please select a scene from the Fleet Command dashboard to view its forensic analysis.
          </p>
          <Link href="/">
            <Button variant="outline">
              <ArrowLeft className="w-4 h-4 mr-2" />
              Back to Fleet Command
            </Button>
          </Link>
        </div>
      </DashboardLayout>
    );
  }

  // Render the existing ClientForensicContent with scene ID and camera from query params
  return (
    <DashboardLayout>
      <ClientForensicContent
        sceneData={null}
        sceneId={sceneId}
        initialCamera={initialCamera}
      />
    </DashboardLayout>
  );
}

// Main page component wrapped in Suspense (REQUIRED for useSearchParams in static export)
export default function ForensicPage() {
  return (
    <ProtectedRoute>
      <Suspense fallback={
        <DashboardLayout>
          <div className="text-center py-12">
            <div className="animate-spin w-8 h-8 border-2 border-blue-500 border-t-transparent rounded-full mx-auto mb-4"></div>
            <p className="text-gray-600">Loading forensic tools...</p>
          </div>
        </DashboardLayout>
      }>
        <ForensicContent />
      </Suspense>
    </ProtectedRoute>
  );
}