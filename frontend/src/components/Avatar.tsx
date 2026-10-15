export function Avatar({ name, photo, size = 38 }: { name: string; photo?: string | null; size?: number }) {
  if (photo) return <img src={photo} alt="" className="shrink-0 rounded-full object-cover" style={{ width: size, height: size }} />
  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-full bg-surface-2 font-extrabold text-ice"
      style={{ width: size, height: size, fontSize: size * 0.37 }}
    >
      {name.slice(0, 1).toUpperCase()}
    </div>
  )
}
