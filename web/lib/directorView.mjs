export function createDirectorRequestCoordinator(fetchImpl) {
  let sequence = 0;
  let activeController = null;

  return {
    async load(storeId) {
      const requestSequence = ++sequence;
      activeController?.abort();
      const controller = new AbortController();
      activeController = controller;

      try {
        const response = await fetchImpl(
          `/api/director?store_id=${encodeURIComponent(storeId)}`,
          { cache: "no-store", signal: controller.signal },
        );
        const payload = await response.json();
        if (requestSequence !== sequence) return { kind: "superseded", storeId };
        if (!response.ok) return { kind: "error", storeId, error: payload.error || "Не удалось загрузить план" };
        if (payload.store_id !== storeId) {
          return { kind: "error", storeId, error: "Director вернул данные другого магазина. Ответ отклонён." };
        }
        return { kind: "success", storeId, data: payload };
      } catch (error) {
        if (requestSequence !== sequence || error?.name === "AbortError") {
          return { kind: "superseded", storeId };
        }
        return { kind: "error", storeId, error: error?.message || "Не удалось загрузить план" };
      }
    },
    cancel() {
      sequence += 1;
      activeController?.abort();
      activeController = null;
    },
  };
}

export function createDirectorMutationCoordinator() {
  let contextGeneration = 0;
  let contextStoreId = "";
  let operationSequence = 0;
  let latestOperationId = 0;
  const latestByLane = new Map();

  return {
    enterContext(storeId) {
      contextGeneration += 1;
      contextStoreId = storeId || "";
      latestOperationId = 0;
      latestByLane.clear();
      return contextGeneration;
    },
    start(lane) {
      const operationId = ++operationSequence;
      latestOperationId = operationId;
      latestByLane.set(lane, operationId);
      return { storeId: contextStoreId, contextGeneration, operationId, lane };
    },
    accepts(token) {
      return token.storeId === contextStoreId
        && token.contextGeneration === contextGeneration
        && token.operationId === latestOperationId;
    },
    finish(token) {
      const current = token.storeId === contextStoreId
        && token.contextGeneration === contextGeneration
        && latestByLane.get(token.lane) === token.operationId;
      if (current) {
        latestByLane.delete(token.lane);
        if (latestOperationId === token.operationId) latestOperationId = 0;
      }
      return current;
    },
  };
}

export function directorViewFlags(data, canManageStore) {
  const states = new Set((data?.sources || []).map((source) => source.state));
  return {
    empty: Boolean(data) && (data.actions || []).length === 0,
    stopped: Boolean(data?.control?.stopped),
    readOnly: Boolean(data) && !canManageStore,
    missing: states.has("missing"),
    stale: states.has("stale"),
    incomplete: states.has("incomplete"),
    sourceError: states.has("error"),
  };
}

export function directorActionAvailability(item, canManageStore) {
  const proposed = item.status === "proposed";
  const measurable = ["approved", "executing", "measured"].includes(item.status) && Boolean(item.measurement);
  const result = {
    canDecide: Boolean(canManageStore && proposed && item.requires_approval),
    canExecute: Boolean(canManageStore && proposed && item.can_execute && item.execution_type === "read_sync"),
    canMeasure: Boolean(canManageStore && measurable),
    unavailableReason: "",
  };
  if (!canManageStore) result.unavailableReason = "Только просмотр: действие доступно владельцу или администратору.";
  else if (proposed && !result.canDecide && !result.canExecute) result.unavailableReason = "Автоматического исполнителя нет — откройте источник и проверьте данные вручную.";
  return result;
}
