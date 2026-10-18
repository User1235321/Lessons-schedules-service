import PlaceholderPage from "../../../components/PlaceholderPage.jsx";

export default function GenerationPage() {
  return (
    <PlaceholderPage
      title="Построение расписания"
      planned={[
        "Режим: один вариант или TOP-N (F_Gen_4)",
        "Запуск расчёта, статус и прогресс с обновлением не реже раза в 2 с (F_Gen_9, NF_Perf_3)",
        "Отмена расчёта (F_Gen_10)",
        "Сообщение об отсутствии решения (F_Gen_11)"
      ]}
    />
  );
}
