import { useCallback, useEffect, useState } from "react";

import { toFormErrors } from "./formErrors.js";

export function useResourceForm({ open, initialValues, validate, onSubmit, errorAliases = {} }) {
  const [values, setValues] = useState(initialValues);
  const [errors, setErrors] = useState({});
  const [formError, setFormError] = useState(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (open) {
      setValues(initialValues);
      setErrors({});
      setFormError(null);
      setSubmitting(false);
    }
  }, [open]);

  const setValue = useCallback((name, value) => {
    setValues((current) => ({ ...current, [name]: value }));
    setErrors((current) => ({ ...current, [name]: undefined }));
  }, []);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFormError(null);

    const found = validate?.(values) ?? {};
    setErrors(found);
    if (Object.keys(found).length > 0) {
      return;
    }

    setSubmitting(true);
    try {
      await onSubmit(values);
    } catch (error) {
      const { fields, form } = toFormErrors(error);
      setErrors(Object.fromEntries(Object.entries(fields).map(([field, message]) => [errorAliases[field] ?? field, message])));
      setFormError(form);
      setSubmitting(false);
    }
  };

  return { values, setValue, errors, formError, submitting, handleSubmit };
}
