import { Button, Paper, Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Typography } from "@mui/material";

import { formatInterval, lessonFormatLabel, WEEKDAYS } from "../project-editor/intervals.js";

const days = WEEKDAYS.map(({ value }) => value);

function compareEntries(a, b) {
  return (a.week === "EVEN") - (b.week === "EVEN") ||
    days.indexOf(a.weekday) - days.indexOf(b.weekday) || a.start_time.localeCompare(b.start_time);
}

export default function EntryTable({ entries, conflicts, onEdit }) {
  const reasons = new Map();
  for (const conflict of conflicts ?? []) {
    for (const id of conflict.entry_ids) {
      if (!reasons.has(id)) reasons.set(id, new Set());
      reasons.get(id).add(conflict.message);
    }
  }
  return (
    <TableContainer component={Paper} variant="outlined">
      <Table size="small" aria-label="Занятия для редактирования">
        <TableHead><TableRow>
          {["День и время", "Занятие", "Формат и аудитория", "Преподаватели", "Действие"].map((label) =>
            <TableCell key={label}>{label}</TableCell>)}
        </TableRow></TableHead>
        <TableBody>
          {[...entries].sort(compareEntries).map((item) => (
            <TableRow key={item.id} sx={reasons.has(item.id) ? { bgcolor: "action.hover", "& > td:first-of-type": {
              borderLeft: 3, borderLeftColor: "warning.main"
            } } : undefined}>
              <TableCell>{formatInterval({ week: item.week, day: item.weekday, start: item.start_time, end: item.end_time })}</TableCell>
              <TableCell>
                <Typography variant="body2">{item.subject_name || "Без названия"}</Typography>
                {item.participant_label}
                {reasons.has(item.id) && (
                  <div>
                    <Typography variant="body2" component="strong" sx={{ fontWeight: 600 }}>Конфликт</Typography>
                    <ul style={{ margin: 0, paddingInlineStart: "1.25rem" }}>
                      {Array.from(reasons.get(item.id), (message) => <li key={message}>{message}</li>)}
                    </ul>
                  </div>
                )}
              </TableCell>
              <TableCell>{[lessonFormatLabel(item.lesson_format), item.room_name].filter(Boolean).join(" · ") || "—"}</TableCell>
              <TableCell>{item.teachers.map((teacher) => teacher.display_name).join(", ") || "—"}</TableCell>
              <TableCell><Button onClick={() => onEdit(item)}>Изменить</Button></TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </TableContainer>
  );
}
