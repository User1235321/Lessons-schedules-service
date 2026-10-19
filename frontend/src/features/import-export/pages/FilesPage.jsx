import PlaceholderPage from "../../../components/PlaceholderPage.jsx";

export default function FilesPage() {
  return (
    <PlaceholderPage
      title="Импорт и экспорт"
      planned={[
        "Загрузка .xlsx, .ods, .csv, .json (F_IO_1)",
        "Сопоставление столбцов и ошибочные строки (F_IO_3, F_IO_4)",
        "История загрузок и выгрузок, повторное скачивание"
      ]}
    />
  );
}
