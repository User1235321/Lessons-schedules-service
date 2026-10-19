import { Container } from "@mui/material";
import { isRouteErrorResponse, useRouteError } from "react-router";

import NotFoundPage from "../pages/NotFoundPage.jsx";
import ErrorState from "./ErrorState.jsx";

function getErrorMessage(error) {
  if (isRouteErrorResponse(error)) {
    return error.data?.message ?? `${error.status} ${error.statusText}`;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Неизвестная ошибка";
}

export default function RouteErrorBoundary({ fullPage = false }) {
  const error = useRouteError();

  if (isRouteErrorResponse(error) && error.status === 404) {
    return <NotFoundPage />;
  }

  const content = (
    <ErrorState
      title="Что-то пошло не так"
      message={getErrorMessage(error)}
      retryLabel="Обновить страницу"
      onRetry={() => window.location.reload()}
    />
  );

  return fullPage ? <Container maxWidth="sm">{content}</Container> : content;
}
