import ReactMarkdown from 'react-markdown'

interface ContentViewerProps {
  content: string
  title?: string
}

export default function ContentViewer({ content, title }: ContentViewerProps) {
  return (
    <div className="bg-white rounded-lg shadow-sm border">
      {title && (
        <div className="px-6 py-4 border-b">
          <h3 className="text-lg font-medium">{title}</h3>
        </div>
      )}
      <div className="px-6 py-4 prose max-w-none">
        <ReactMarkdown>{content}</ReactMarkdown>
      </div>
    </div>
  )
}
