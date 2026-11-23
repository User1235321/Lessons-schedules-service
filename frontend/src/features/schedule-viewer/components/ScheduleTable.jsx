import {
  Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow
} from "@mui/material";

import { WEEKDAYS, lessonFormatLabel, lessonTypeLabel } from "../../project-editor/intervals.js";

const dayOrder = WEEKDAYS.map(({ value }) => value);
const columns = ["День", "Время", "Дисциплина", "Тип занятия", "Формат", "Для кого", "Преподаватели", "Аудитория"];

export default function ScheduleTable({ entries, week }) {
  const lessons = entries.filter((entry) => entry.week === week).sort((left, right) =>
    dayOrder.indexOf(left.weekday) - dayOrder.indexOf(right.weekday) ||
    left.start_time.localeCompare(right.start_time) ||
    left.end_time.localeCompare(right.end_time)
  );

  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small" aria-label="Занятия выбранной недели">
        <TableHead>
          <TableRow>{columns.map((title) => <TableCell key={title}>{title}</TableCell>)}</TableRow>
        </TableHead>
        <TableBody>
          {lessons.map((lesson) => (
            <TableRow key={lesson.id}>
              <TableCell>{WEEKDAYS.find(({ value }) => value === lesson.weekday)?.label}</TableCell>
              <TableCell sx={{ whiteSpace: "nowrap" }}>{lesson.start_time}–{lesson.end_time}</TableCell>
              <TableCell>{lesson.subject_name || "—"}</TableCell>
              <TableCell>{lessonTypeLabel(lesson.lesson_type) || "—"}</TableCell>
              <TableCell>{lessonFormatLabel(lesson.lesson_format) || "—"}</TableCell>
              <TableCell>{lesson.participant_label || "—"}</TableCell>
              <TableCell>{lesson.teachers.map((teacher) => teacher.display_name).join(", ") || "—"}</TableCell>
              <TableCell>{lesson.room_name || "—"}</TableCell>
            </TableRow>
          ))}
          {lessons.length === 0 && (
            <TableRow><TableCell colSpan={columns.length} align="center" sx={{ py: 3 }}>
              На этой неделе занятий нет.
            </TableCell></TableRow>
          )}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
