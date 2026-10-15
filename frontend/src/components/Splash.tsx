import { motion } from 'framer-motion'

export function Splash({ error }: { error?: string | null }) {
  return (
    <div className="fixed inset-0 z-20 flex flex-col items-center justify-end gap-4 bg-black px-10 pb-16">
      <motion.img
        src="/media/logo.jpg"
        alt=""
        className="absolute inset-x-0 top-10 mx-auto h-[70%] w-full max-w-[480px] object-cover"
        initial={{ opacity: 0, scale: 0.92 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.7 }}
      />
      <div className="relative font-display text-[28px] font-bold tracking-[6px]">ELT</div>
      {error ? (
        <div className="relative text-center text-[13px] text-muted">
          Не удалось подключиться. Откройте приложение заново из бота.
        </div>
      ) : (
        <>
          <div className="relative h-1.5 w-[220px] overflow-hidden rounded-full bg-track">
            <motion.div
              className="h-full rounded-full bg-red"
              initial={{ width: '4%' }}
              animate={{ width: '100%' }}
              transition={{ duration: 2.2, ease: 'easeInOut' }}
            />
          </div>
          <div className="relative text-xs text-muted">Загрузка…</div>
        </>
      )}
    </div>
  )
}
