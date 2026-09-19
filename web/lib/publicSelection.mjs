export const PUBLIC_MODULES = [
  { code: "cards", label: "AI Card Factory", note: "Контент из подтверждённых фактов", status: "Доступно после подключения WB" },
  { code: "profit", label: "Profit Center", note: "Детерминированная экономика", status: "Доступно после подключения WB" },
  { code: "director", label: "AI Director", note: "Решения и доказательства", status: "Доступно после подключения WB" },
  { code: "fbo", label: "Smart FBO", note: "Остатки и поставки", status: "Доступно частично" },
];

export const PUBLIC_CHANNELS = {
  wb: {
    label: "Wildberries",
    status: "Можно настроить после входа",
    availability: "implemented",
    title: "Wildberries — первая доступная площадка",
    text: "В текущей версии есть подключение, чтение данных и подтверждение действий для Wildberries. Работа опубликованной версии подтверждается отдельной проверкой.",
    items: ["Подключение после входа и MFA", "Права проверяет сервер", "Запись только после отдельного подтверждения"],
  },
  ozon: {
    label: "Ozon",
    status: "Запланировано",
    availability: "planned",
    title: "Следующая площадка после проверенного WB-контура",
    text: "Ozon присутствует в плане и legacy desktop, но рабочая web-интеграция ещё не реализована.",
    items: ["Общий каталог — запланировано", "Финансовая сверка — запланировано", "Подключение недоступно"],
  },
  yandex: {
    label: "Яндекс Маркет",
    status: "Запланировано",
    availability: "planned",
    title: "Общий контур товара и экономики",
    text: "Подключение появится после отдельной проверки API, capability-контракта и прав доступа.",
    items: ["Адаптер — запланировано", "Синхронизация — запланировано", "Подключение недоступно"],
  },
  kaspi: {
    label: "Kaspi.kz",
    status: "Запланировано · discovery",
    availability: "planned",
    title: "Казахстан — отдельный проверяемый пилот",
    text: "До реализации требуется проверить API, договорную модель, валюту и экономику маршрута.",
    items: ["Discovery API — запланировано", "KZT и сверка — запланировано", "Подключение недоступно"],
  },
  uzum: {
    label: "Uzum Market",
    status: "Запланировано",
    availability: "planned",
    title: "Локализация после отдельного discovery",
    text: "Uzum остаётся в дорожной карте; текущий интерфейс не выдаёт его за подключённую возможность.",
    items: ["Локализация — запланировано", "Экономика возвратов — запланировано", "Подключение недоступно"],
  },
};

export const planForScale = { 1: "pro", 3: "pro", 10: "business" };

const validPlans = new Set(["pro", "business"]);
const validChannels = new Set(["wb", "start"]);
const validStores = new Set(["1", "3", "10"]);
const validModules = new Set(PUBLIC_MODULES.map(({ code }) => code));
const validInterests = new Set(
  Object.entries(PUBLIC_CHANNELS)
    .filter(([, item]) => item.availability === "planned")
    .map(([code]) => code),
);

export function normalizeRegistrationIntent(params) {
  const plan = params.get("plan");
  const channel = params.get("channel");
  const stores = params.get("stores");
  const interest = params.get("interest");
  const moduleValues = typeof params.getAll === "function"
    ? params.getAll("modules")
    : [params.get("modules")];
  const modules = [...new Set(
    moduleValues
      .flatMap((value) => (value || "").split(","))
      .filter((code) => validModules.has(code)),
  )];

  return {
    plan: validPlans.has(plan) ? plan : "trial",
    channel: validChannels.has(channel) ? channel : "start",
    stores: validStores.has(stores) ? stores : "1",
    modules,
    interest: validInterests.has(interest) ? interest : "",
  };
}

function selectionParams(intent) {
  const params = new URLSearchParams({
    plan: intent.plan,
    channel: intent.channel,
    stores: String(intent.stores),
    modules: intent.modules.join(","),
  });
  if (intent.interest) params.set("interest", intent.interest);
  return params;
}

export function buildRegistrationIntent({ channel, modules, stores, plan, interest = "" }) {
  return `/register?${selectionParams({ channel, modules, stores, plan, interest })}`;
}

export function buildPublicSelectionHref(intent) {
  return `/?${selectionParams(intent)}#bundle`;
}

export function restorePublicSelection(params) {
  const normalized = normalizeRegistrationIntent(params);
  return {
    channel: normalized.interest || "wb",
    modules: normalized.modules,
    stores: Number(normalized.stores),
  };
}
