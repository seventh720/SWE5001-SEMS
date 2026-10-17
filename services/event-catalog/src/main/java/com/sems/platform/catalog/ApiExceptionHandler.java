package com.sems.platform.catalog;

import java.net.URI;
import java.util.LinkedHashMap;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.http.ProblemDetail;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

@RestControllerAdvice
public class ApiExceptionHandler {

    @ExceptionHandler(org.springframework.http.converter.HttpMessageNotReadableException.class)
    ProblemDetail invalidBody() {
        return problem(HttpStatus.BAD_REQUEST, "Invalid request body",
                "Check the JSON field types and use ISO 8601 timestamps with a time zone.");
    }

    @ExceptionHandler(org.springframework.orm.ObjectOptimisticLockingFailureException.class)
    ProblemDetail concurrentUpdate() {
        return problem(HttpStatus.CONFLICT, "Event changed",
                "This record was changed by another request. Reload before editing.");
    }

    @ExceptionHandler(org.springframework.dao.DataIntegrityViolationException.class)
    ProblemDetail closedOrganization(org.springframework.dao.DataIntegrityViolationException exception) {
        for(Throwable cause=exception;cause!=null;cause=cause.getCause())
            if(cause instanceof org.hibernate.exception.ConstraintViolationException violation && "organization_closure_fence".equals(violation.getConstraintName()))
                return problem(HttpStatus.CONFLICT,"Organization closing","Organization closure has started. New event changes are no longer allowed.");
        throw exception;
    }

    @ExceptionHandler(ResponseStatusException.class)
    ProblemDetail requestFailure(ResponseStatusException exception) {
        return exception.getBody();
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    ProblemDetail invalidParameter(MethodArgumentTypeMismatchException exception) {
        return problem(HttpStatus.BAD_REQUEST, "Invalid request parameter",
                "Invalid value for parameter: " + exception.getName());
    }




    @ExceptionHandler(MethodArgumentNotValidException.class)
    ProblemDetail validation(MethodArgumentNotValidException exception) {
        ProblemDetail detail = problem(
                HttpStatus.BAD_REQUEST,
                "Validation failed",
                "One or more request fields are invalid");
        Map<String, String> errors = new LinkedHashMap<>();
        exception.getBindingResult().getFieldErrors().forEach(error ->
                errors.putIfAbsent(error.getField(), error.getDefaultMessage()));
        detail.setProperty("fieldErrors", errors);
        return detail;
    }

    private ProblemDetail problem(HttpStatus status, String title, String detailMessage) {
        ProblemDetail detail = ProblemDetail.forStatusAndDetail(status, detailMessage);
        detail.setTitle(title);
        detail.setType(URI.create("about:blank"));
        return detail;
    }
}
