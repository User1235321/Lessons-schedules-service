import { useEffect, useState } from "react";
import {
  Alert,
  Box,
  Button,
  Checkbox,
  FormControlLabel,
  Paper,
  Stack,
  Typography
} from "@mui/material";
import { useParams } from "react-router";

import { api } from "../../../api/client.js";
import ErrorState from "../../../components/ErrorState.jsx";
import LoadingState from "../../../components/LoadingState.jsx";
import { CRITERION_TYPES } from "../constraintModel.js";

function normalizeCriteria(saved) {
  const known = new Map(saved.map((criterion) => [criterion.criterion_type, criterion]));
  return CRITERION_TYPES.map((type, index) => ({
    criterion_type: type.value,
    priority: known.get(type.value)?.priority ?? index + 1,
    is_active: known.get(type.value)?.is_active ?? false
  }))
    .sort((left, right) =>
      Number(right.is_active) - Number(left.is_active) || left.priority - right.priority)
    .map((criterion, index) => ({ ...criterion, priority: index + 1 }));
}

function OptimizationEditor({ projectId }) {
  const [criteria, setCriteria] = useState(null);
  const [loadError, setLoadError] = useState(null);
  const [saveError, setSaveError] = useState(null);
  const [saving, setSaving] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [reload, setReload] = useState(0);
  const endpoint = `/projects/${encodeURIComponent(projectId)}/optimization-criteria`;

  useEffect(() => {
    let active = true;
    api.get(endpoint).then((saved) => {
      if (active) {
        setCriteria(normalizeCriteria(saved));
        setLoadError(null);
      }
    }).catch((error) => {
      if (active) setLoadError(error);
    });
    return () => { active = false; };
  }, [endpoint, reload]);

  const update = (next) => {
    setCriteria(normalizeCriteria(next));
    setDirty(true);
    setSaveError(null);
  };

  const toggle = (type, checked) => {
    update(criteria.map((criterion) => criterion.criterion_type === type
      ? { ...criterion, is_active: checked }
      : criterion
    ));
  };

  const move = (type, direction) => {
    const next = [...criteria];
    const index = next.findIndex((criterion) => criterion.criterion_type === type);
    const target = index + direction;
    if (target < 0 || target >= next.length || !next[target].is_active) return;
    [next[index], next[target]] = [next[target], next[index]];
    update(next.map((criterion, position) => ({ ...criterion, priority: position + 1 })));
  };

  const save = async () => {
    setSaving(true);
    setSaveError(null);
    try {
      const saved = await api.put(endpoint, { criteria });
      setCriteria(normalizeCriteria(saved));
      setDirty(false);
    } catch (error) {
      setSaveError(error.message);
    } finally {
      setSaving(false);
    }
  };

  if (loadError) {
    return (
      <ErrorState
        title="Не удалось загрузить критерии оптимизации"
        message={loadError.message}
        onRetry={() => {
          setLoadError(null);
          setCriteria(null);
          setReload((current) => current + 1);
        }}
      />
    );
  }

  return (
    <Box sx={{ py: 2 }}>
      <Typography component="h2" variant="h5" sx={{ mb: 1 }}>
        Оптимизация
      </Typography>
      <Typography color="text.secondary" sx={{ mb: 2 }}>
        Выбор критериев оптимизации. Порядок приоритетов критериев определяет,
        какие условия учитываются первыми при сравнении расписаний.
      </Typography>
      {!criteria ? <LoadingState label="Загружаем критерии" /> : (
        <Stack spacing={2}>
          <Paper variant="outlined" sx={{ p: 2 }}>
            <Stack spacing={1}>
              {criteria.map((criterion, index) => {
                const label = CRITERION_TYPES.find((type) =>
                  type.value === criterion.criterion_type)?.label ?? criterion.criterion_type;
                return (
                  <Stack
                    key={criterion.criterion_type}
                    direction={{ xs: "column", sm: "row" }}
                    spacing={1}
                    sx={{ alignItems: { sm: "center" }, justifyContent: "space-between" }}
                  >
                    <FormControlLabel
                      label={label}
                      control={
                        <Checkbox
                          checked={criterion.is_active}
                          disabled={saving}
                          onChange={(event) => toggle(criterion.criterion_type, event.target.checked)}
                        />
                      }
                    />
                    {criterion.is_active && (
                      <Stack direction="row" spacing={1} sx={{ alignItems: "center" }}>
                        <Typography variant="body2">Приоритет {index + 1}</Typography>
                        <Button
                          size="small"
                          disabled={saving || index === 0}
                          onClick={() => move(criterion.criterion_type, -1)}
                          aria-label={`Повысить приоритет: ${label}`}
                        >
                          Вверх
                        </Button>
                        <Button
                          size="small"
                          disabled={saving || index === criteria.filter((item) => item.is_active).length - 1}
                          onClick={() => move(criterion.criterion_type, 1)}
                          aria-label={`Понизить приоритет: ${label}`}
                        >
                          Вниз
                        </Button>
                      </Stack>
                    )}
                  </Stack>
                );
              })}
            </Stack>
          </Paper>
          {saveError && <Alert severity="error">{saveError}</Alert>}
          <Stack direction="row" spacing={2} sx={{ justifyContent: "flex-end" }}>
            <Button variant="contained" onClick={save} disabled={!dirty || saving}>
              Сохранить критерии
            </Button>
          </Stack>
        </Stack>
      )}
    </Box>
  );
}

export default function OptimizationPage() {
  const { projectId } = useParams();
  return <OptimizationEditor key={projectId} projectId={projectId} />;
}
