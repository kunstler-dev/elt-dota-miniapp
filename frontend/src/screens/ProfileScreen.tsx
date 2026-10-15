import { useQuery } from '@tanstack/react-query'
import { lazy, Suspense, useState } from 'react'

import { ProfileView } from '../components/ProfileView'
import { ScreenTitle } from '../components/ui'
import { api } from '../lib/api'
import { useGame } from '../store/game'

const AdminScreen = lazy(() => import('./AdminScreen').then((m) => ({ default: m.AdminScreen })))

export function ProfileScreen() {
  const { data } = useQuery({ queryKey: ['profile', 'me'], queryFn: () => api.profile() })
  const isAdmin = useGame((s) => s.me?.user.is_admin)
  const [admin, setAdmin] = useState(false)
  return (
    <div className="flex flex-col gap-3 px-4 pt-3.5 pb-6">
      <ScreenTitle title="Профиль" />
      {data ? <ProfileView p={data} /> : <div className="p-8 text-center text-sm text-muted">Загружаем…</div>}
      {isAdmin && (
        <button
          type="button"
          onClick={() => setAdmin(true)}
          className="press rounded-[14px] border border-line-2 bg-surface py-3 text-sm font-extrabold"
        >
          Админка
        </button>
      )}
      <Suspense fallback={null}>{admin && <AdminScreen onClose={() => setAdmin(false)} />}</Suspense>
    </div>
  )
}
