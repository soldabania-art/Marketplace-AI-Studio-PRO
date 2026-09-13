import { Suspense } from "react";
import D01DesignReference from "../../components/D01DesignReference";
import "./d01.css";

export const metadata = {
  title: "TROVENDI · D01 Direction B",
  description:
    "Выбранное направление B TROVENDI и связанный демонстрационный маршрут.",
  robots: { index: false, follow: false },
};

function LoadingFrame() {
  return (
    <main className="d01 d01-final">
      <div className="d01-boot">Загружаем TROVENDI…</div>
    </main>
  );
}

export default function DesignReferencePage() {
  return (
    <Suspense fallback={<LoadingFrame />}>
      <D01DesignReference />
    </Suspense>
  );
}
