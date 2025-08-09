import React from 'react'
import { Move, SplitSquareHorizontal, Zap, Layers } from 'lucide-react'
import type { DiffMode } from '../App'

interface DiffToolbarProps {
  diffMode: DiffMode
  onDiffModeChange: (mode: DiffMode) => void
}

const DiffToolbar: React.FC<DiffToolbarProps> = ({
  diffMode,
  onDiffModeChange
}) => {
  const modes = [
    {
      type: 'maskOverlay' as const,
      icon: Layers,
      label: 'Mask Overlay',
      description: 'Show changes as colored overlay'
    },
    {
      type: 'swipe' as const,
      icon: Move,
      label: 'Swipe',
      description: 'Drag to reveal before/after'
    },
    {
      type: 'sideBySide' as const,
      icon: SplitSquareHorizontal,
      label: 'Side by Side',
      description: 'Split view comparison'
    },
    {
      type: 'flicker' as const,
      icon: Zap,
      label: 'Flicker',
      description: 'Animated before/after toggle'
    }
  ]

  return (
    <div className="space-y-3">
      {/* Mode buttons */}
      <div className="grid grid-cols-2 gap-2">
        {modes.map(mode => {
          const Icon = mode.icon
          const isActive = diffMode.type === mode.type
          
          return (
            <button
              key={mode.type}
              onClick={() => onDiffModeChange({ type: mode.type })}
              className={`
                flex flex-col items-center gap-1 p-3 rounded-lg border transition-all
                ${isActive 
                  ? 'bg-blue-50 border-blue-200 text-blue-700' 
                  : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50'
                }
              `}
              title={mode.description}
            >
              <Icon className="w-4 h-4" />
              <span className="text-xs font-medium">{mode.label}</span>
            </button>
          )
        })}
      </div>

      {/* Mode-specific controls */}
      {diffMode.type === 'flicker' && (
        <div className="bg-white rounded-lg p-3 border border-gray-200">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Flicker Speed
          </label>
          <input
            type="range"
            min="0.5"
            max="3"
            step="0.1"
            value={diffMode.flickerSpeed || 2}
            onChange={(e) => onDiffModeChange({
              ...diffMode,
              flickerSpeed: parseFloat(e.target.value)
            })}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>Slow</span>
            <span>{(diffMode.flickerSpeed || 2).toFixed(1)}s</span>
            <span>Fast</span>
          </div>
        </div>
      )}

      {diffMode.type === 'swipe' && (
        <div className="bg-white rounded-lg p-3 border border-gray-200">
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Swipe Position
          </label>
          <input
            type="range"
            min="0"
            max="100"
            value={diffMode.swipePosition || 50}
            onChange={(e) => onDiffModeChange({
              ...diffMode,
              swipePosition: parseInt(e.target.value)
            })}
            className="w-full"
          />
          <div className="flex justify-between text-xs text-gray-500 mt-1">
            <span>Before</span>
            <span>{diffMode.swipePosition || 50}%</span>
            <span>After</span>
          </div>
        </div>
      )}

      {/* Layer opacity controls for mask overlay */}
      {diffMode.type === 'maskOverlay' && (
        <div className="bg-white rounded-lg p-3 border border-gray-200 space-y-3">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Base Image Opacity
            </label>
            <input
              type="range"
              min="0"
              max="100"
              defaultValue="70"
              className="w-full"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Change Mask Opacity
            </label>
            <input
              type="range"
              min="0"
              max="100"
              defaultValue="60"
              className="w-full"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Polygon Outline Opacity
            </label>
            <input
              type="range"
              min="0"
              max="100"
              defaultValue="80"
              className="w-full"
            />
          </div>
        </div>
      )}

      {/* Quick actions */}
      <div className="flex gap-2">
        <button className="button button-ghost text-xs flex-1">
          Reset View
        </button>
        <button className="button button-ghost text-xs flex-1">
          Fit to Changes
        </button>
      </div>
    </div>
  )
}

export default DiffToolbar