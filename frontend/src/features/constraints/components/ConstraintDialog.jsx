import { resourceApi } from "../../project-editor/api.js";
import ResourceFormDialog from "../../project-editor/components/ResourceFormDialog.jsx";
import { useResourceForm } from "../../project-editor/useResourceForm.js";
import {
  initialConstraintValues,
  toConstraintRequest,
  validateConstraint
} from "../constraintModel.js";
import ConstraintFields from "./ConstraintFields.jsx";

export default function ConstraintDialog({ open, item, projectId, options, onClose, onSaved }) {
  const form = useResourceForm({
    open,
    initialValues: initialConstraintValues(item, options),
    validate: (values) => validateConstraint(values, options),
    onSubmit: async (values) => {
      const api = resourceApi(projectId, "constraints");
      const body = toConstraintRequest(values);
      const saved = item ? await api.update(item.id, body) : await api.create(body);
      onSaved(saved);
    }
  });

  return (
    <ResourceFormDialog
      open={open}
      title={item ? "Изменить ограничение" : "Новое ограничение"}
      submitLabel={item ? "Сохранить" : "Добавить"}
      form={form}
      onClose={onClose}
      maxWidth="md"
    >
      <ConstraintFields
        values={form.values}
        errors={form.errors}
        setValue={form.setValue}
        options={options}
      />
    </ResourceFormDialog>
  );
}
