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