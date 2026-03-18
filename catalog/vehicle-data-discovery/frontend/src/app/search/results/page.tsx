/**
 * Search Results Page - Display Search Results
 * 
 * Shows semantic search results with scene cards, similarity scores,
 * and filtering options. Supports text and visual similarity search.
 * 
 * @route /search/results?q={query}&mode={behavioral|visual}
 */
import { Suspense } from "react"
import DashboardLayout from "@/components/layout/DashboardLayout"
import SearchResultsContent from "@/components/search/SearchResultsContent"

export default function SearchResultsPage() {
  return (
    <DashboardLayout>
      <Suspense fallback={<div>Loading search results...</div>}>
        <SearchResultsContent />
      </Suspense>
    </DashboardLayout>
  )
}