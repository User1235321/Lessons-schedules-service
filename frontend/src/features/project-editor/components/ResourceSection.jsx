import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Box,
  Button,
  Paper,
  Stack,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Typography
} from "@mui/material";

import ConfirmDialog from "../../../components/ConfirmDialog.jsx";
import ErrorState from "../../../components/ErrorState.jsx";
import LoadingState from "../../../components/LoadingState.jsx";
import { resourceApi } from "../api.js";

// Раздел редактора: таблица ресурсов проекта с добавлением, изменением и удалением.
// FormDialog({ open, item, projectId, onClose, onSaved }) — диалог раздела. item === null
// для создания, dialogProps передаются диалогу как есть. columns: [{ label, render(item) }]. itemLabel(item) — название для подписей
export default function ResourceSection({
  title,
  description,
  projectId,
  resource,
  columns,
  itemLabel,
  addLabel,
  emptyText,
  deleteText,
  FormDialog,
  dialogProps,
  rowActions = []
}) {
  const api = useMemo(() => resourceApi(projectId, resource), [projectId, resource]);
  const [items, setItems] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [dialog, setDialog] = useState({ open: false, item: null });
  const [deletion, setDeletion] = useState({ open: false, item: null });
  const [action, setAction] = useState({ index: null, itemId: null });

  const load = useCallback(async () => {
    setItems(null);
    setLoadError(null);
    try {
      setItems(await api.list());
    } catch (error) {
      setLoadError(error);
    }
  }, [api]);

  useEffect(() => {
    load();
  }, [load]);

  const replaceItem = (saved) =>
    setItems((current) =>
      current.some((item) => item.id === saved.id)
        ? current.map((item) => (item.id === saved.id ? saved : item))
        : [...current, saved]
    );

  const handleSaved = (saved) => {
    replaceItem(saved);
    setDialog((current) => ({ ...current, open: false }));
  };

  const handleDelete = async () => {
    const { item } = deletion;
    try {
      await api.remove(item.id);
    } catch (error) {
      // Уже удалено в другой вкладке: для пользователя результат тот же
      if (error.code !== "NOT_FOUND") {
        throw error;
      }
    }
    setItems((current) => current.filter((candidate) => candidate.id !== item.id));
  };

  return (
    <Box sx={{ py: 2 }}>
      <Stack
        direction="row"
        spacing={2}
        sx={{ alignItems: "center", justifyContent: "space-between", mb: 1 }}
      >
        <Typography component="h2" variant="h5">
          {title}
        </Typography>
        <Button variant="contained" onClick={() => setDialog({ open: true, item: null })}>
          {addLabel}
        </Button>
      </Stack>
      {description && (
        <Typography color="text.secondary" sx={{ mb: 2 }}>
          {description}
        </Typography>
      )}

      {loadError ? (
        <ErrorState title="Не удалось загрузить данные" message={loadError.message} onRetry={load} />
      ) : items === null ? (
        <LoadingState label="Загружаем данные" />
      ) : items.length === 0 ? (
        <Typography color="text.secondary">{emptyText}</Typography>
      ) : (
        <TableContainer component={Paper} variant="outlined">
          <Table aria-label={title}>
            <TableHead>
              <TableRow>
                {columns.map((column) => (
                  <TableCell key={column.label}>{column.label}</TableCell>
                ))}
                <TableCell align="right">Действия</TableCell>
              </TableRow>
            </TableHead>
            <TableBody>
              {items.map((item) => (
                <TableRow key={item.id}>
                  {columns.map((column) => (
                    <TableCell key={column.label}>{column.render(item)}</TableCell>
                  ))}
                  <TableCell align="right" sx={{ whiteSpace: "nowrap" }}>
                    {rowActions.map((rowAction, index) => (
                      <Button
                        key={rowAction.label}
                        size="small"
                        aria-label={`${rowAction.label}: ${itemLabel(item)}`}
                        onClick={() => setAction({ index, itemId: item.id })}
                      >
                        {rowAction.label}
                      </Button>
                    ))}
                    <Button
                      size="small"
                      aria-label={`Изменить: ${itemLabel(item)}`}
                      onClick={() => setDialog({ open: true, item })}
                    >
                      Изменить
                    </Button>
                    <Button
                      size="small"
                      color="error"
                      aria-label={`Удалить: ${itemLabel(item)}`}
                      onClick={() => setDeletion({ open: true, item })}
                    >
                      Удалить
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </TableContainer>
      )}

      <FormDialog
        open={dialog.open}
        item={dialog.item}
        projectId={projectId}
        onClose={() => setDialog((current) => ({ ...current, open: false }))}
        onSaved={handleSaved}
        {...dialogProps}
      />
      {rowActions.map(({ label, Dialog }, index) => (
        <Dialog
          key={label}
          open={action.index === index}
          // Строка берётся из текущего списка: диалог видит изменения, которые сам внёс
          item={items?.find((item) => item.id === action.itemId) ?? null}
          projectId={projectId}
          onClose={() => setAction((current) => ({ ...current, index: null }))}
          onChanged={replaceItem}
        />
      ))}
      <ConfirmDialog
        open={deletion.open}
        title="Удалить?"
        onConfirm={handleDelete}
        onClose={() => setDeletion((current) => ({ ...current, open: false }))}
      >
        {deletion.item && deleteText(deletion.item)}
      </ConfirmDialog>
    </Box>
  );
}
