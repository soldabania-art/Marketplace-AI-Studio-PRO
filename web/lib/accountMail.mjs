export function verificationRequestMessage(delivery) {
  if (delivery === 'not_required') return 'Email уже подтверждён.'
  if (delivery === 'email_provider_not_configured') return 'Отправка писем пока недоступна. Попробуйте позже.'
  if (delivery === 'queued') return 'Письмо поставлено в очередь отправки. Проверьте почту через несколько минут.'
  return 'Запрос принят. Доставка письма пока не подтверждена.'
}

// Construction never submits a token. Only an explicit confirmation can do so.
export function createEmailConfirmation(token, request) {
  let pending = null
  let confirmed = false
  return {
    confirm() {
      if (confirmed) return Promise.resolve({ confirmed: true })
      if (pending) return pending
      if (!token) return Promise.resolve({ error: 'В ссылке нет кода подтверждения. Запросите новое письмо в аккаунте.' })
      pending = (async () => {
        try {
          const response = await request('/api/auth/email-verification', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ action: 'confirm', token }),
          })
          const payload = await response.json()
          if (response.ok && payload.email_verified === true) {
            confirmed = true
            return { confirmed: true }
          }
          if (response.status === 400) return { error: 'Ссылка недействительна, уже использована или просрочена. Проверьте статус email в аккаунте; при необходимости запросите новое письмо.' }
          return { error: 'Подтверждение не получено. Попробуйте позже или проверьте статус email в аккаунте.' }
        } catch {
          return { error: 'Ответ сервера не получен. Email мог быть подтверждён. Проверьте его статус в аккаунте перед повтором.' }
        }
      })()
      pending.finally(() => { pending = null })
      return pending
    },
  }
}
