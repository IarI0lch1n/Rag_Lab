import logging

from contextlib import contextmanager

import httpx

from langfuse import (
    Langfuse,
    propagate_attributes,
)

from src.config import settings


logger = logging.getLogger(
    "advisor.langfuse"
)


class _NoopObservation:

    trace_id = None
    id = None

    @property
    def observation_id(self):
        return None

    def child_trace_context(self):
        return None

    def update(
        self,
        **_kwargs,
    ) -> None:
        return None


class _SafeObservation:

    def __init__(
        self,
        observation,
    ) -> None:
        self._observation = observation

    @property
    def trace_id(self):
        return getattr(
            self._observation,
            "trace_id",
            None,
        )

    @property
    def id(self):
        return getattr(
            self._observation,
            "id",
            None,
        )

    @property
    def observation_id(self):
        return self.id

    def child_trace_context(
        self,
    ) -> dict | None:

        trace_id = self.trace_id
        observation_id = self.id

        if (
            not trace_id
            or not observation_id
        ):
            return None

        return {
            "trace_id": trace_id,
            "parent_span_id": observation_id,
        }

    def update(
        self,
        **kwargs,
    ) -> None:

        try:
            self._observation.update(
                **kwargs
            )

        except Exception:
            logger.exception(
                (
                    "Could not update "
                    "Langfuse observation."
                )
            )


class LangfuseService:

    def __init__(
        self,
    ) -> None:
        self._client: (
            Langfuse
            | None
        ) = None

    @property
    def enabled(
        self,
    ) -> bool:
        return bool(
            settings.langfuse_enabled
        )

    @property
    def configured(
        self,
    ) -> bool:
        return bool(
            settings.langfuse_public_key
            and settings.langfuse_secret_key
        )

    @property
    def client(
        self,
    ) -> Langfuse:

        if not self.enabled:
            raise RuntimeError(
                "Langfuse is disabled."
            )

        if not self.configured:
            raise RuntimeError(
                (
                    "Langfuse credentials "
                    "are not configured."
                )
            )

        if self._client is None:

            logger.info(
                (
                    "Initializing Langfuse client | "
                    "base_url=%s | "
                    "environment=%s"
                ),
                settings.langfuse_base_url,
                (
                    settings
                    .langfuse_tracing_environment
                ),
            )

            self._client = Langfuse(
                public_key=(
                    settings
                    .langfuse_public_key
                ),
                secret_key=(
                    settings
                    .langfuse_secret_key
                ),
                base_url=(
                    settings
                    .langfuse_base_url
                ),
                timeout=max(
                    1,
                    int(
                        settings
                        .langfuse_timeout_seconds
                    ),
                ),
                tracing_enabled=True,
                environment=(
                    settings
                    .langfuse_tracing_environment
                ),
            )

        return self._client

    #
    # PUBLIC API
    #

    def test_connection(
        self,
    ) -> tuple[
        bool,
        str,
    ]:

        if not self.enabled:
            return (
                False,
                "Langfuse is disabled.",
            )

        if not self.configured:
            return (
                False,
                (
                    "Langfuse credentials "
                    "are not configured."
                ),
            )

        endpoint = (
            settings
            .langfuse_base_url
            .rstrip("/")
            + "/api/public/projects"
        )

        try:
            response = httpx.get(
                endpoint,
                auth=httpx.BasicAuth(
                    settings
                    .langfuse_public_key,
                    settings
                    .langfuse_secret_key,
                ),
                timeout=(
                    settings
                    .langfuse_timeout_seconds
                ),
                headers={
                    "Accept": (
                        "application/json"
                    ),
                },
            )

            response.raise_for_status()

            payload = response.json()

            projects = (
                payload.get(
                    "data",
                    [],
                )
                if isinstance(
                    payload,
                    dict,
                )
                else []
            )

            project_names = [
                str(
                    project.get(
                        "name",
                        "",
                    )
                ).strip()
                for project in projects
                if (
                    isinstance(
                        project,
                        dict,
                    )
                    and project.get(
                        "name"
                    )
                )
            ]

            if project_names:
                message = (
                    "Connected to Langfuse API. "
                    "Project: "
                    f"{', '.join(project_names)}"
                )

            else:
                message = (
                    "Connected to Langfuse API."
                )

            logger.info(
                message
            )

            return (
                True,
                message,
            )

        except Exception as exc:
            logger.exception(
                (
                    "Langfuse API "
                    "connection test failed."
                )
            )

            return (
                False,
                str(exc),
            )

    #
    # ROOT TRACE
    #

    @contextmanager
    def trace(
        self,
        *,
        name: str,
        input_data=None,
        session_id: (
            str
            | None
        ) = None,
        metadata: (
            dict
            | None
        ) = None,
        tags: (
            list[str]
            | None
        ) = None,
    ):

        if not self.enabled:
            yield _NoopObservation()
            return

        try:
            manager = (
                self.client
                .start_as_current_observation(
                    as_type="span",
                    name=name,
                    input=input_data,
                    metadata=metadata,
                )
            )

            raw_observation = (
                manager.__enter__()
            )

        except Exception:
            logger.exception(
                (
                    "Could not start "
                    "Langfuse trace | "
                    "name=%s"
                ),
                name,
            )

            yield _NoopObservation()
            return

        observation = (
            _SafeObservation(
                raw_observation
            )
        )

        propagation_manager = None

        propagation_kwargs = {
            "trace_name": name,
        }

        if session_id:
            propagation_kwargs[
                "session_id"
            ] = session_id

        if tags:
            propagation_kwargs[
                "tags"
            ] = tags

        try:
            propagation_manager = (
                propagate_attributes(
                    **propagation_kwargs
                )
            )

            propagation_manager.__enter__()

        except Exception:
            logger.exception(
                (
                    "Could not propagate "
                    "Langfuse attributes | "
                    "name=%s"
                ),
                name,
            )

            propagation_manager = None

        error = None

        try:
            yield observation

        except BaseException as exc:
            error = exc

            observation.update(
                level="ERROR",
                status_message=(
                    str(exc)[:1000]
                ),
            )

            raise

        finally:

            if (
                propagation_manager
                is not None
            ):
                try:
                    propagation_manager.__exit__(
                        (
                            type(error)
                            if error
                            else None
                        ),
                        error,
                        (
                            error.__traceback__
                            if error
                            else None
                        ),
                    )

                except Exception:
                    logger.exception(
                        (
                            "Could not close "
                            "Langfuse attribute "
                            "context."
                        )
                    )

            try:
                manager.__exit__(
                    (
                        type(error)
                        if error
                        else None
                    ),
                    error,
                    (
                        error.__traceback__
                        if error
                        else None
                    ),
                )

            except Exception:
                logger.exception(
                    (
                        "Could not close "
                        "Langfuse trace | "
                        "name=%s"
                    ),
                    name,
                )

            if (
                settings
                .langfuse_flush_after_request
            ):
                self.flush()

    #
    # CHILD OBSERVATION
    #

    @contextmanager
    def observation(
        self,
        *,
        name: str,
        as_type: str = "span",
        input_data=None,
        metadata: (
            dict
            | None
        ) = None,
        model: (
            str
            | None
        ) = None,
        model_parameters: (
            dict
            | None
        ) = None,
        trace_context: (
            dict
            | None
        ) = None,
    ):

        if not self.enabled:
            yield _NoopObservation()
            return

        try:
            manager = (
                self.client
                .start_as_current_observation(
                    as_type=as_type,
                    name=name,
                    input=input_data,
                    metadata=metadata,
                    model=model,
                    model_parameters=(
                        model_parameters
                    ),
                    trace_context=(
                        trace_context
                    ),
                )
            )

            raw_observation = (
                manager.__enter__()
            )

        except Exception:
            logger.exception(
                (
                    "Could not start "
                    "Langfuse observation | "
                    "name=%s | type=%s"
                ),
                name,
                as_type,
            )

            yield _NoopObservation()
            return

        observation = (
            _SafeObservation(
                raw_observation
            )
        )

        error = None

        try:
            yield observation

        except BaseException as exc:
            error = exc

            observation.update(
                level="ERROR",
                status_message=(
                    str(exc)[:1000]
                ),
            )

            raise

        finally:
            try:
                manager.__exit__(
                    (
                        type(error)
                        if error
                        else None
                    ),
                    error,
                    (
                        error.__traceback__
                        if error
                        else None
                    ),
                )

            except Exception:
                logger.exception(
                    (
                        "Could not close "
                        "Langfuse observation | "
                        "name=%s"
                    ),
                    name,
                )

    def flush(
        self,
    ) -> None:

        if (
            not self.enabled
            or self._client is None
        ):
            return

        try:
            self._client.flush()

        except Exception:
            logger.exception(
                (
                    "Could not flush "
                    "Langfuse events."
                )
            )

    def shutdown(
        self,
    ) -> None:

        if self._client is None:
            return

        try:
            self._client.shutdown()

        except Exception:
            logger.exception(
                (
                    "Could not shut down "
                    "Langfuse client cleanly."
                )
            )


langfuse_service = (
    LangfuseService()
)