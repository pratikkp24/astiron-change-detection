import React, { useState } from 'react'
import { ChevronDown, Info, Download, FolderOpen, Copy, BarChart3 } from 'lucide-react'
import type { RunData, PairData, DiffMode } from '../App'
import { formatArea, copyToClipboard, downloadJson, generateSubmissionName } from '../api/files'
import DiffToolbar from './DiffToolbar'

interface LeftPanelProps {
  runs: RunData[]
  selectedRun: string | null
  selectedPair: string | null
  currentPair: PairData | null
  diffMode: DiffMode
  onRunChange: (runId: string) => void
  onPairChange: (pairId: string) => void
  onDiffModeChange: (mode: DiffMode) => void
}

const LeftPanel: React.FC<LeftPanelProps> = ({
  runs,
  selectedRun,
  selectedPair,
  currentPair,
  diffMode,
  onRunChange,
  onPairChange,
  onDiffModeChange
}) => {
  const [expandedSections, setExpandedSections] = useState<Set<string>>(
    new Set(['selector', 'diff', 'stats'])
  )
  const [selectedPolygon, setSelectedPolygon] = useState<any>(null)

  const toggleSection = (section: string) => {
    const newExpanded = new Set(expandedSections)
    if (newExpanded.has(section)) {
      newExpanded.delete(section)
    } else {
      newExpanded.add(section)
    }
    setExpandedSections(newExpanded)
  }

  const handleCopyPath = async () => {
    if (currentPair) {
      const path = `outputs/${selectedRun}/${selectedPair}`
      await copyToClipboard(path)
      // Could show a toast notification here
    }
  }

  const handleDownloadGeoJSON = () => {
    if (currentPair?.geojson) {
      downloadJson(currentPair.geojson, `${currentPair.pairId}_changes.geojson`)
    }
  }

  const handleCopySubmissionName = async () => {
    const submissionName = generateSubmissionName()
    await copyToClipboard(submissionName)
  }

  const currentRun = runs.find(r => r.runId === selectedRun)
  const stats = currentPair?.manifest.statistics

  return (
    <div className="w-80 h-full bg-gray-50 border-r border-gray-200 flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-200">
        <h1 className="text-xl font-semibold text-gray-900">
          PS-10 Change Detection
        </h1>
        <p className="text-sm text-gray-500 mt-1">
          Visual QA Interface
        </p>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        
        {/* Run & Pair Selector */}
        <div className="card-frosted p-4 fade-in">
          <button
            onClick={() => toggleSection('selector')}
            className="flex items-center justify-between w-full text-left"
          >
            <h3 className="font-medium text-gray-900">Data Selection</h3>
            <ChevronDown 
              className={`w-4 h-4 text-gray-500 transition-transform ${
                expandedSections.has('selector') ? 'rotate-180' : ''
              }`}
            />
          </button>
          
          {expandedSections.has('selector') && (
            <div className="mt-4 space-y-3">
              {/* Run selector */}
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">
                  Run
                </label>
                <select
                  value={selectedRun || ''}
                  onChange={(e) => onRunChange(e.target.value)}
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                >
                  {runs.map(run => (
                    <option key={run.runId} value={run.runId}>
                      {run.runId} ({run.pairs.length} pairs)
                    </option>
                  ))}
                </select>
              </div>

              {/* Pair selector */}
              {currentRun && (
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    Pair
                  </label>
                  <select
                    value={selectedPair || ''}
                    onChange={(e) => onPairChange(e.target.value)}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
                  >
                    {currentRun.pairs.map(pair => (
                      <option key={pair.pairId} value={pair.pairId}>
                        {pair.pairId}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Diff Mode Controls */}
        <div className="card-frosted p-4">
          <button
            onClick={() => toggleSection('diff')}
            className="flex items-center justify-between w-full text-left"
          >
            <h3 className="font-medium text-gray-900">Comparison Mode</h3>
            <ChevronDown 
              className={`w-4 h-4 text-gray-500 transition-transform ${
                expandedSections.has('diff') ? 'rotate-180' : ''
              }`}
            />
          </button>
          
          {expandedSections.has('diff') && (
            <div className="mt-4">
              <DiffToolbar
                diffMode={diffMode}
                onDiffModeChange={onDiffModeChange}
              />
            </div>
          )}
        </div>

        {/* Statistics */}
        {stats && (
          <div className="card-frosted p-4">
            <button
              onClick={() => toggleSection('stats')}
              className="flex items-center justify-between w-full text-left"
            >
              <h3 className="font-medium text-gray-900">Statistics</h3>
              <ChevronDown 
                className={`w-4 h-4 text-gray-500 transition-transform ${
                  expandedSections.has('stats') ? 'rotate-180' : ''
                }`}
              />
            </button>
            
            {expandedSections.has('stats') && (
              <div className="mt-4 space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="bg-white rounded-lg p-3 shadow-sm">
                    <div className="text-2xl font-bold text-blue-600">
                      {stats.total_polygons.toLocaleString()}
                    </div>
                    <div className="text-xs text-gray-500">Polygons</div>
                  </div>
                  
                  <div className="bg-white rounded-lg p-3 shadow-sm">
                    <div className="text-2xl font-bold text-green-600">
                      {formatArea(stats.change_area_m2)}
                    </div>
                    <div className="text-xs text-gray-500">Changed Area</div>
                  </div>
                </div>

                <div className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <span className="text-gray-600">Total pixels:</span>
                    <span className="font-medium">{stats.total_pixels.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Changed pixels:</span>
                    <span className="font-medium">{stats.change_pixels.toLocaleString()}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Change %:</span>
                    <span className="font-medium">
                      {((stats.change_pixels / stats.total_pixels) * 100).toFixed(2)}%
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Largest polygon:</span>
                    <span className="font-medium">{formatArea(stats.largest_area_m2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-gray-600">Mean polygon:</span>
                    <span className="font-medium">{formatArea(stats.mean_area_m2)}</span>
                  </div>
                </div>

                {/* Change intensity indicator */}
                <div className="mt-3">
                  <div className="flex items-center justify-between text-sm mb-1">
                    <span className="text-gray-600">Change Intensity</span>
                    <span className="font-medium">
                      {stats.change_area_km2 < 0.1 ? 'Low' : 
                       stats.change_area_km2 < 1.0 ? 'Medium' : 'High'}
                    </span>
                  </div>
                  <div className="w-full bg-gray-200 rounded-full h-2">
                    <div 
                      className={`h-2 rounded-full ${
                        stats.change_area_km2 < 0.1 ? 'bg-green-500' :
                        stats.change_area_km2 < 1.0 ? 'bg-amber-500' : 'bg-red-500'
                      }`}
                      style={{ 
                        width: `${Math.min(100, (stats.change_area_km2 / 2.0) * 100)}%` 
                      }}
                    />
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {/* Inspector */}
        {selectedPolygon && (
          <div className="card-frosted p-4">
            <h3 className="font-medium text-gray-900 mb-3 flex items-center gap-2">
              <Info className="w-4 h-4" />
              Polygon Inspector
            </h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-600">ID:</span>
                <span className="font-medium">{selectedPolygon.properties?.change_id}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Area:</span>
                <span className="font-medium">
                  {formatArea(selectedPolygon.properties?.area_m2 || 0)}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-600">Perimeter:</span>
                <span className="font-medium">
                  {(selectedPolygon.properties?.perimeter_m || 0).toFixed(0)} m
                </span>
              </div>
            </div>
          </div>
        )}

        {/* Export Tools */}
        <div className="card-frosted p-4">
          <h3 className="font-medium text-gray-900 mb-3">Export & Tools</h3>
          <div className="space-y-2">
            <button
              onClick={handleCopyPath}
              className="button button-ghost w-full justify-start"
            >
              <Copy className="w-4 h-4" />
              Copy Path
            </button>
            
            <button
              onClick={() => alert('Open your file explorer and navigate to the copied path')}
              className="button button-ghost w-full justify-start"
            >
              <FolderOpen className="w-4 h-4" />
              Reveal in Explorer
            </button>
            
            {currentPair?.geojson && (
              <button
                onClick={handleDownloadGeoJSON}
                className="button button-ghost w-full justify-start"
              >
                <Download className="w-4 h-4" />
                Download GeoJSON
              </button>
            )}
            
            <button
              onClick={handleCopySubmissionName}
              className="button button-ghost w-full justify-start"
            >
              <BarChart3 className="w-4 h-4" />
              Copy Submission Name
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export default LeftPanel