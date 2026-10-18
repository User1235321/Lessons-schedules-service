import PlaceholderPage from "../../../components/PlaceholderPage.jsx";

export default function ProjectSettingsPage() {
  return (
    <PlaceholderPage
      title="Настройки проекта"
      planned={[
        "Дни нечётной и чётной недели (F_Data_1)",
        "Начало занятий: по часам или с шагом (F_Data_2)",
        "Единая или индивидуальная длительность (F_Data_3)"
      ]}
    />
  );
}
