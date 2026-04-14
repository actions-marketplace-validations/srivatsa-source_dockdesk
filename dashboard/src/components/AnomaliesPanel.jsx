import React from 'react'
import { AlertTriangle, Clock, ServerOff, FileX } from 'lucide-react'

// AnomaliesPanel.jsx - Orchestration Metrics Visualization
const AnomaliesPanel = ({ metrics }) => {
  if (!metrics) {
    return (
      <div className="bg-white rounded-lg shadow p-6">
        <h2 className="text-xl font-semibold mb-4 text-gray-800">Orchestration Anomalies</h2>
        <p className="text-gray-500">No orchestration metrics found for this run.</p>
      </div>
    )
  }

  const {
    execution_time_seconds = 0,
    files_discovered = 0,
    files_analyzed = 0,
    model_used = 'Unknown',
    reasoning_model_used = 'Unknown',
    pass_fail_distribution = {},
    risk_distribution = {}
  } = metrics

  return (
    <div className="space-y-6">
      <div className="bg-white rounded-lg shadow p-6 border-l-4 border-amber-500">
        <h2 className="text-xl font-semibold mb-4 text-gray-800 flex items-center">
          <AlertTriangle className="mr-2 text-amber-500" />
          Orchestration execution & Anomalies
        </h2>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="p-4 bg-gray-50 rounded-md">
            <div className="text-sm text-gray-500 flex items-center mb-1">
              <Clock className="w-4 h-4 mr-1" /> Total Execution
            </div>
            <div className="text-2xl font-bold">{execution_time_seconds}s</div>
          </div>
          
          <div className="p-4 bg-gray-50 rounded-md">
            <div className="text-sm text-gray-500 flex items-center mb-1">
              <FileX className="w-4 h-4 mr-1" /> Pipeline File Dropoff
            </div>
            <div className="text-2xl font-bold">{files_discovered} <span className="text-sm font-normal text-gray-400">found</span> → {files_analyzed} <span className="text-sm font-normal text-gray-400">analyzed</span></div>
          </div>
          
          <div className="p-4 bg-gray-50 rounded-md">
            <div className="text-sm text-gray-500 flex items-center mb-1">
              <ServerOff className="w-4 h-4 mr-1" /> Selected Nodes
            </div>
            <div className="text-md font-semibold text-blue-600 block">{model_used}</div>
            <div className="text-md font-semibold text-purple-600 block mt-1">{reasoning_model_used}</div>
          </div>
        </div>

        <div>
           <h3 className="font-semibold text-gray-700 mb-2">Outcome Tally vs Risk Assessed</h3>
           <div className="flex space-x-4 mb-2">
              <span className="px-3 py-1 bg-green-100 text-green-800 rounded">PASS: {pass_fail_distribution.PASS || 0}</span>
              <span className="px-3 py-1 bg-red-100 text-red-800 rounded">FAIL: {pass_fail_distribution.FAIL || 0}</span>
           </div>
           <div className="flex space-x-4">
              <span className="px-3 py-1 bg-red-100 text-red-800 rounded text-sm">HIGH: {risk_distribution.HIGH || 0}</span>
              <span className="px-3 py-1 bg-amber-100 text-amber-800 rounded text-sm">MEDIUM: {risk_distribution.MEDIUM || 0}</span>
              <span className="px-3 py-1 bg-blue-100 text-blue-800 rounded text-sm">LOW: {risk_distribution.LOW || 0}</span>
           </div>
        </div>
      </div>
    </div>
  )
}

export default AnomaliesPanel
