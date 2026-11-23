import { useState } from "react";
import {
  Box, Button, Link, List, ListItem, ListItemText, Stack, TextField, Typography
} from "@mui/material";
import { Link as RouterLink, useNavigate, useParams } from "react-router";

import { paths } from "../../../app/paths.js";
import { useAuth } from "../../auth/AuthProvider.jsx";
import { readScheduleHistory } from "../scheduleHistory.js";

const uuid = /^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$/i;
const addedDate = new Intl.DateTimeFormat("ru-RU", { dateStyle: "short", timeStyle: "short" });

export default function SchedulesPage() {
  const { projectId } = useParams();
  const { user } = useAuth();
  const navigate = useNavigate();
  const [value, setValue] = useState("");
  const [invalid, setInvalid] = useState(false);
  const [history] = useState(() => readScheduleHistory(user.id, projectId));

  function openSchedule(event) {
    event.preventDefault();
    const id = value.trim();
    if (!uuid.test(id)) {
      setInvalid(true);
      return;
    }
    navigate(paths.schedule(projectId, id.toLowerCase()));
  }

  return (
    <Stack spacing={3} sx={{ py: 2 }}>
      <Typography component="h2" variant="h5">Расписания</Typography>
      <Stack component="form" onSubmit={openSchedule} direction={{ xs: "column", sm: "row" }}
        spacing={1} sx={{ alignItems: { sm: "flex-start" } }}>
        <TextField label="ID сохранённого расписания" size="small" value={value}
          onChange={(event) => { setValue(event.target.value); setInvalid(false); }}
          error={invalid} helperText={invalid ? "Введите полный UUID расписания" : null}
          sx={{ width: { sm: 360 } }} />
        <Button type="submit" variant="outlined">Открыть по ID</Button>
      </Stack>
      <Box>
        <Typography component="h3" variant="h6">Расписания в этом браузере</Typography>
        {history.length === 0 ? (
          <Typography color="text.secondary">
            Здесь появятся результаты расчётов и расписания, которые вы открыли в этом проекте.
          </Typography>
        ) : (
          <List disablePadding>
            {history.map((record) => (
              <ListItem key={record.id} divider disableGutters>
                <ListItemText
                  primary={
                    <Link component={RouterLink} to={paths.schedule(projectId, record.id)}>
                      {record.source === "IMPORTED" ? "Загруженное расписание" : `Вариант ${record.index}`}
                      {" · "}{record.id}
                    </Link>
                  }
                  secondary={`Добавлено ${addedDate.format(record.addedAt)}`}
                  sx={{ overflowWrap: "anywhere" }}
                />
              </ListItem>
            ))}
          </List>
        )}
      </Box>
    </Stack>
  );
}
