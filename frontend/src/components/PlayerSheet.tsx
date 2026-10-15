import { useQuery } from '@tanstack/react-query'
import { motion } from 'framer-motion'

import { api } from '../lib/api'
import { Icon } from './icons'
import { ProfileView } from './ProfileView'

/** Another player's profile on top of the leaderboard. */
export function PlayerSheet({ id, onClose }: { id: number; onClose: () => void }) {
  const { data, isError } = useQuery({ queryKey: ['profile', id], queryFn: () => api.profile(id) })
  return (
    <motion.div className="fixed inset-0 z-40 flex items-end bg-black/70" initial={{ opacity: 0 }} animate={{ opacity: 1 }} onClick={onClose}>
      <motion.div
        className="no-scrollbar mx-auto max-h-[92%] w-full max-w-[480px] overflow-y-auto rounded-t-3xl border-t border-line bg-ground px-4 pt-3 pb-[max(20px,env(safe-area-inset-bottom))]"
        initial={{ y: 60 }}
        animate={{ y: 0 }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-2 flex justify-end">
          <button type="button" aria-label="Закрыть" onClick={onClose} className="flex h-9 w-9 items-center justify-center rounded-xl border border-line bg-surface">
            <Icon name="back" size={18} className="rotate-[-90deg]" />
          </button>
        </div>
        {data ? <ProfileView p={data} /> : <div className="p-8 text-center text-sm text-muted">{isError ? 'Игрок не найден' : 'Загружаем…'}</div>}
      </motion.div>
    </motion.div>
  )
}
