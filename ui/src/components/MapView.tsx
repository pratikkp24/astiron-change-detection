import React, { useEffect, useRef, useState } from 'react'
import Map, { Source, Layer } from 'react-map-gl/maplibre'
import type { MapRef } from 'react-map-gl/maplibre'
import type { PairData, DiffMode } from '../App'
import { getRasterUrl } from '../api/files'

interface MapViewProps {
  pair: PairData | null
  diffMode: DiffMode
  onDiffModeChange: (mode: DiffMode) => void
}

const MapView: React.FC<MapViewProps> = ({
  pair,
  diffMode,
  onDiffModeChange
}) => {
  const mapRef = useRef<MapRef>(null)
  const [viewState, setViewState] = useState({
    longitude: 74.3909,
    latitude: 34.0531,
    zoom: 10
  })
  const [flickerState, setFlickerState] = useState<'before' | 'after'>('before')

  // Flicker effect
  useEffect(() => {
    if (diffMode.type === 'flicker') {
      const interval = setInterval(() => {
        setFlickerState(prev => prev === 'before' ? 'after' : 'before')
      }, (diffMode.flickerSpeed || 2) * 1000)
      
      return () => clearInterval(interval)
    }
  }, [diffMode])

  // Fit to changes when pair changes
  useEffect(() => {
    if (pair?.geojson && mapRef.current) {
      try {
        // Calculate bounds from GeoJSON
        const features = pair.geojson.features || []
        if (features.length > 0) {
          let minLng = Infinity, minLat = Infinity
          let maxLng = -Infinity, maxLat = -Infinity
          
          features.forEach((feature: any) => {
            if (feature.geometry?.coordinates) {
              const coords = feature.geometry.coordinates[0] // Assuming polygon
              coords.forEach(([lng, lat]: [number, number]) => {
                minLng = Math.min(minLng, lng)
                maxLng = Math.max(maxLng, lng)
                minLat = Math.min(minLat, lat)
                maxLat = Math.max(maxLat, lat)
              })
            }
          })
          
          if (isFinite(minLng)) {
            mapRef.current.fitBounds(
              [[minLng, minLat], [maxLng, maxLat]],
              { padding: 50, duration: 1000 }
            )
          }
        }
      } catch (error) {
        console.warn('Failed to fit bounds:', error)
      }
    }
  }, [pair])

  if (!pair) {
    return (
      <div className="flex-1 flex items-center justify-center bg-gray-100">
        <div className="text-center">
          <div className="text-gray-400 text-6xl mb-4">🗺️</div>
          <h3 className="text-lg font-medium text-gray-900 mb-2">No Data Selected</h3>
          <p className="text-gray-600">Select a run and pair to view results</p>
        </div>
      </div>
    )
  }

  const runId = 'demo_run' // This should come from props
  const pairId = pair.pairId

  // Layer configurations
  const changePolygonLayer = {
    id: 'change-polygons-fill',
    type: 'fill' as const,
    paint: {
      'fill-color': '#ef4444',
      'fill-opacity': 0.3
    }
  }

  const changePolygonOutlineLayer = {
    id: 'change-polygons-outline',
    type: 'line' as const,
    paint: {
      'line-color': '#dc2626',
      'line-width': 2,
      'line-opacity': 0.8
    }
  }

  return (
    <div className="flex-1 relative">
      <Map
        ref={mapRef}
        {...viewState}
        onMove={evt => setViewState(evt.viewState)}
        style={{ width: '100%', height: '100%' }}
        mapStyle={{
          version: 8,
          sources: {},
          layers: [
            {
              id: 'background',
              type: 'background',
              paint: {
                'background-color': '#f8f9fa'
              }
            }
          ]
        }}
        attributionControl={false}
      >
        {/* Change polygons */}
        {pair.geojson && (
          <Source
            id="change-polygons"
            type="geojson"
            data={pair.geojson}
          >
            <Layer {...changePolygonLayer} />
            <Layer {...changePolygonOutlineLayer} />
          </Source>
        )}
      </Map>

      {/* Overlay UI */}
      <div className="absolute top-4 right-4 space-y-2">
        {/* Mode indicator */}
        <div className="card-frosted px-3 py-2">
          <div className="text-sm font-medium text-gray-900 capitalize">
            {diffMode.type.replace(/([A-Z])/g, ' $1')}
          </div>
          {diffMode.type === 'flicker' && (
            <div className="text-xs text-gray-600">
              Showing: {flickerState}
            </div>
          )}
        </div>

        {/* Stats overlay */}
        {pair.manifest.statistics && (
          <div className="card-frosted p-3 space-y-1">
            <div className="text-sm font-medium text-gray-900">
              {pair.manifest.statistics.total_polygons} Changes
            </div>
            <div className="text-xs text-gray-600">
              {pair.manifest.statistics.change_area_km2.toFixed(2)} km² affected
            </div>
          </div>
        )}
      </div>

      {/* Swipe control */}
      {diffMode.type === 'swipe' && (
        <div 
          className="absolute top-0 bottom-0 w-1 bg-white shadow-lg cursor-ew-resize z-10"
          style={{ left: `${diffMode.swipePosition || 50}%` }}
          onMouseDown={(e) => {
            const startX = e.clientX
            const startPosition = diffMode.swipePosition || 50
            
            const handleMouseMove = (e: MouseEvent) => {
              const rect = e.currentTarget?.parentElement?.getBoundingClientRect()
              if (rect) {
                const newPosition = Math.max(0, Math.min(100, 
                  startPosition + ((e.clientX - startX) / rect.width) * 100
                ))
                onDiffModeChange({ ...diffMode, swipePosition: newPosition })
              }
            }
            
            const handleMouseUp = () => {
              document.removeEventListener('mousemove', handleMouseMove)
              document.removeEventListener('mouseup', handleMouseUp)
            }
            
            document.addEventListener('mousemove', handleMouseMove)
            document.addEventListener('mouseup', handleMouseUp)
          }}
        >
          <div className="absolute top-1/2 left-1/2 transform -translate-x-1/2 -translate-y-1/2 bg-white rounded-full p-2 shadow-md">
            <div className="w-2 h-8 bg-gray-400 rounded"></div>
          </div>
        </div>
      )}

      {/* Loading overlay */}
      {!pair.geojson && (
        <div className="absolute inset-0 bg-white bg-opacity-75 flex items-center justify-center">
          <div className="text-center">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600 mx-auto mb-2"></div>
            <p className="text-sm text-gray-600">Loading map data...</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default MapView