export function SkeletonTableRows({ rows = 5 }) {
  return (
    <div className="bg-white rounded-2xl border border-[#e4ede4] overflow-hidden shadow-sm">
      <div className="h-10 bg-[#f5f8f5] border-b border-[#e8ede8]" />
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="flex gap-4 px-4 py-3 border-b border-[#f0f4f0] last:border-0 animate-pulse">
          <div className="h-4 bg-[#eef4ee] rounded w-20 flex-shrink-0" />
          <div className="h-4 bg-[#eef4ee] rounded w-28 flex-shrink-0" />
          <div className="h-4 bg-[#eef4ee] rounded flex-1" />
          <div className="h-4 bg-[#eef4ee] rounded w-8 flex-shrink-0" />
          <div className="h-4 bg-[#eef4ee] rounded w-8 flex-shrink-0" />
        </div>
      ))}
    </div>
  )
}

export function SkeletonCards({ count = 4 }) {
  return (
    <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-2xl border border-[#e4ede4] p-5 animate-pulse space-y-3 bg-white">
          <div className="h-10 w-10 bg-[#eef4ee] rounded-xl" />
          <div className="h-4 bg-[#eef4ee] rounded w-3/4" />
          <div className="h-3 bg-[#eef4ee] rounded w-1/2" />
          <div className="h-3 bg-[#eef4ee] rounded w-1/3" />
          <div className="h-7 bg-[#eef4ee] rounded-lg" />
        </div>
      ))}
    </div>
  )
}

export function SkeletonStatCards() {
  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
      {Array.from({ length: 4 }).map((_, i) => (
        <div key={i} className="rounded-2xl border border-[#e4ede4] p-5 animate-pulse bg-white">
          <div className="h-3 bg-[#eef4ee] rounded w-2/3 mb-3" />
          <div className="h-8 bg-[#eef4ee] rounded w-1/2" />
        </div>
      ))}
    </div>
  )
}

export function SkeletonChart({ height = 220 }) {
  return (
    <div className="bg-white rounded-2xl border border-[#e4ede4] p-6 shadow-sm animate-pulse">
      <div className="h-4 bg-[#eef4ee] rounded w-40 mb-4" />
      <div className="bg-[#eef4ee] rounded-xl" style={{ height }} />
    </div>
  )
}
