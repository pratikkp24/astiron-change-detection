import React, { useState, useEffect } from 'react'
import LeftPanel from './components/LeftPanel'
import MapView from './components/MapView'
import { loadAvailableRuns } from './api/files'

export interface RunData {
  runId: string
  pairs: PairData[]
}

export interface PairData {
  pairId: string
  manifest: {
    pair_id: string
    outputs: {
      change_mask: string
      shapefile: string
      geojson: string
    }
    statistics: {
      total_pixels: number
      change_pixels: number
      change_area_m2: number
      change_area_km2: number
      total_polygons: number
      largest_area_m2: number
      mean_area_m2: number
    }
  }
  geojson?: any
}

export interface DiffMode {
  type: 'swipe' | 'sideBySide' | 'flicker' | 'maskOverlay'
  flickerSpeed?: number
  swipePosition?: number
}

function App() {
  const [runs, setRuns] = useState<RunData[]>([])
  const [selectedRun, setSelectedRun] = useState<string | null>(null)
  const [selectedPair, setSelectedPair] = useState<string | null>(null)
  const [diffMode, setDiffMode] = useState<DiffMode>({ type: 'maskOverlay' })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setLoading(true)
      const availableRuns = await loadAvailableRuns()
      setRuns(availableRuns)
      
      // Auto-select first run and pair if available
      if (availableRuns.length > 0) {
        const firstRun = availableRuns[0]
        setSelectedRun(firstRun.runId)
        
        if (firstRun.pairs.length > 0) {
          setSelectedPair(firstRun.pairs[0].pairId)
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load data')
    } finally {
      setLoading(false)
    }
  }

  const getCurrentPair = (): PairData | null => {
    if (!selectedRun || !selectedPair) return null
    
    const run = runs.find(r => r.runId === selectedRun)
    if (!run) return null
    
    return run.pairs.find(p => p.pairId === selectedPair) || null
  }

  const handleRunChange = (runId: string) => {
    setSelectedRun(runId)
    
    // Auto-select first pair in new run
    const run = runs.find(r => r.runId === runId)
    if (run && run.pairs.length > 0) {
      setSelectedPair(run.pairs[0].pairId)
    } else {
      setSelectedPair(null)
    }
  }

  const handlePairChange = (pairId: string) => {
    setSelectedPair(pairId)
  }

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">Loading change detection results...</p>
        </div>
      </div>
    )
  }

  if (error) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="text-red-500 text-6xl mb-4">⚠️</div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">Failed to Load Data</h2>
          <p className="text-gray-600 mb-4">{error}</p>
          <button 
            onClick={loadData}
            className="button button-primary"
          >
            Try Again
          </button>
          <div className="mt-6 text-sm text-gray-500">
            <p>Make sure you have:</p>
            <ul className="list-disc list-inside mt-2 space-y-1">
              <li>Copied a run to <code>public/outputs/</code></li>
              <li>Run the pipeline successfully</li>
              <li>Generated GeoJSON files</li>
            </ul>
          </div>
        </div>
      </div>
    )
  }

  if (runs.length === 0) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="text-center max-w-md">
          <div className="text-gray-400 text-6xl mb-4">📊</div>
          <h2 className="text-xl font-semibold text-gray-900 mb-2">No Results Found</h2>
          <p className="text-gray-600 mb-4">
            No change detection results are available for visualization.
          </p>
          <div className="text-sm text-gray-500">
            <p>To get started:</p>
            <ol className="list-decimal list-inside mt-2 space-y-1 text-left">
              <li>Run the change detection pipeline</li>
              <li>Copy results to <code>ui/public/outputs/</code></li>
              <li>Refresh this page</li>
            </ol>
          </div>
        </div>
      </div>
    )
  }

  const currentPair = getCurrentPair()

  return (
    <div className="h-full flex">
      <LeftPanel
        runs={runs}
        selectedRun={selectedRun}
        selectedPair={selectedPair}
        currentPair={currentPair}
        diffMode={diffMode}
        onRunChange={handleRunChange}
        onPairChange={handlePairChange}
        onDiffModeChange={setDiffMode}
      />
      
      <div className="flex-1">
        <MapView
          pair={currentPair}
          diffMode={diffMode}
          onDiffModeChange={setDiffMode}
        />
      </div>
    </div>
  )
}

export default App