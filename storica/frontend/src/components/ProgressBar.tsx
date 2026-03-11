interface ProgressBarProps {
  progress: number
  message?: string
  status?: 'running' | 'completed' | 'error' | 'pending'
}

export default function ProgressBar({ progress, message, status = 'running' }: ProgressBarProps) {
  const getStatusColor = () => {
    switch (status) {
      case 'completed':
        return 'bg-green-500'
      case 'error':
        return 'bg-red-500'
      case 'pending':
        return 'bg-gray-400'
      default:
        return 'bg-primary-500'
    }
  }

  return (
    <div className="w-full">
      <div className="flex justify-between mb-1">
        <span className="text-sm font-medium text-gray-700">
          {message || 'Processing...'}
        </span>
        <span className="text-sm font-medium text-gray-700">{progress}%</span>
      </div>
      <div className="w-full bg-gray-200 rounded-full h-2.5">
        <div
          className={`h-2.5 rounded-full transition-all duration-300 ${getStatusColor()}`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  )
}
