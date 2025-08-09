/**
 * File API for loading local change detection results.
 * Works with static files served by Vite dev server.
 */

import type { RunData, PairData } from '../App'

/**
 * Load available runs from the outputs directory.
 * In development, files should be copied to public/outputs/
 */
export async function loadAvailableRuns(): Promise<RunData[]> {
  try {
    // Try to load the runs index file
    const response = await fetch('/outputs/index.json')
    
    if (response.ok) {
      const index = await response.json()
      return await Promise.all(
        index.runs.map(async (runId: string) => {
          return await loadRun(runId)
        })
      )
    }
  } catch (error) {
    console.warn('No index.json found, scanning for runs manually')
  }

  // Fallback: try to load common run patterns
  const runs: RunData[] = []
  const commonRunIds = [
    'RUN_20241201_120000',
    'RUN_20241201_100000', 
    'pair_001',
    'demo_run'
  ]

  for (const runId of commonRunIds) {
    try {
      const run = await loadRun(runId)
      if (run.pairs.length > 0) {
        runs.push(run)
      }
    } catch (error) {
      // Ignore failed attempts
      console.debug(`Failed to load run ${runId}:`, error)
    }
  }

  return runs
}

/**
 * Load a specific run's data
 */
export async function loadRun(runId: string): Promise<RunData> {
  const pairs: PairData[] = []
  
  // Try to load common pair patterns
  const commonPairIds = [
    'pair_001',
    'pair_002', 
    'pair_003',
    's2_kashmir',
    'liss4_delhi'
  ]

  for (const pairId of commonPairIds) {
    try {
      const pair = await loadPair(runId, pairId)
      pairs.push(pair)
    } catch (error) {
      // Ignore failed attempts
      console.debug(`Failed to load pair ${pairId} from run ${runId}:`, error)
    }
  }

  if (pairs.length === 0) {
    throw new Error(`No pairs found for run ${runId}`)
  }

  return {
    runId,
    pairs
  }
}

/**
 * Load a specific pair's data
 */
export async function loadPair(runId: string, pairId: string): Promise<PairData> {
  const basePath = `/outputs/${runId}/${pairId}`
  
  // Load manifest
  const manifestResponse = await fetch(`${basePath}/manifest.json`)
  if (!manifestResponse.ok) {
    throw new Error(`Failed to load manifest for ${runId}/${pairId}`)
  }
  
  const manifest = await manifestResponse.json()
  
  // Load GeoJSON if available
  let geojson = null
  try {
    const geojsonPath = `${basePath}/${manifest.outputs.geojson}`
    const geojsonResponse = await fetch(geojsonPath)
    if (geojsonResponse.ok) {
      geojson = await geojsonResponse.json()
    }
  } catch (error) {
    console.warn(`Failed to load GeoJSON for ${pairId}:`, error)
  }

  return {
    pairId,
    manifest,
    geojson
  }
}

/**
 * Get the URL for a raster file
 */
export function getRasterUrl(runId: string, pairId: string, filename: string): string {
  return `/outputs/${runId}/${pairId}/${filename}`
}

/**
 * Copy text to clipboard
 */
export async function copyToClipboard(text: string): Promise<void> {
  if (navigator.clipboard) {
    await navigator.clipboard.writeText(text)
  } else {
    // Fallback for older browsers
    const textArea = document.createElement('textarea')
    textArea.value = text
    document.body.appendChild(textArea)
    textArea.select()
    document.execCommand('copy')
    document.body.removeChild(textArea)
  }
}

/**
 * Download data as JSON file
 */
export function downloadJson(data: any, filename: string): void {
  const blob = new Blob([JSON.stringify(data, null, 2)], { 
    type: 'application/json' 
  })
  
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}

/**
 * Open file/folder in system explorer (hint for user)
 */
export function showInExplorer(path: string): void {
  // This is just a hint - browsers can't actually open file explorer
  // Show a notification or modal with the path
  alert(`Path: ${path}\n\nNote: Copy this path and open it in your file explorer manually.`)
}

/**
 * Format file size
 */
export function formatFileSize(bytes: number): string {
  const units = ['B', 'KB', 'MB', 'GB']
  let size = bytes
  let unitIndex = 0
  
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024
    unitIndex++
  }
  
  return `${size.toFixed(1)} ${units[unitIndex]}`
}

/**
 * Format area values
 */
export function formatArea(areaM2: number): string {
  if (areaM2 < 10000) {
    return `${areaM2.toFixed(0)} m²`
  } else if (areaM2 < 1000000) {
    return `${(areaM2 / 10000).toFixed(1)} ha`
  } else {
    return `${(areaM2 / 1000000).toFixed(2)} km²`
  }
}

/**
 * Generate submission filename
 */
export function generateSubmissionName(teamName: string = 'TEAMNAME'): string {
  const date = new Date()
  const day = date.getDate().toString().padStart(2, '0')
  const month = date.toLocaleString('en', { month: 'short' })
  const year = date.getFullYear()
  
  return `PS10_${day}-${month}-${year}_${teamName}.zip`
}