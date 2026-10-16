package com.sems.platform.identity;

import com.sems.platform.identity.internal.application.DuplicateUserException;
import com.sems.platform.identity.internal.application.InvalidCredentialsException;
import com.sems.platform.identity.internal.application.UserNotFoundException;
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

    @ExceptionHandler(ResponseStatusException.class)
    ProblemDetail requestFailure(ResponseStatusException exception) {
        return exception.getBody();
    }

    @ExceptionHandler(MethodArgumentTypeMismatchException.class)
    ProblemDetail invalidParameter(MethodArgumentTypeMismatchException exception) {
        return problem(HttpStatus.BAD_REQUEST, "Invalid request parameter",
                "Invalid value for parameter: " + exception.getName());
    }

    @ExceptionHandler(org.springframework.dao.DuplicateKeyException.class)
    ProblemDetail duplicateKey() { return problem(HttpStatus.CONFLICT,"Already exists","This organization or membership already exists. Reload and retry."); }

    @ExceptionHandler(DuplicateUserException.class)
    ProblemDetail duplicateUser(DuplicateUserException exception) {
        return problem(HttpStatus.CONFLICT, "Account already exists", exception.getMessage());
    }

    @ExceptionHandler(InvalidCredentialsException.class)
    ProblemDetail invalidCredentials() {
        return problem(HttpStatus.UNAUTHORIZED, "Authentication failed", "Invalid email or password");
    }

    @ExceptionHandler(UserNotFoundException.class)
    ProblemDetail userNotFound(UserNotFoundException exception) {
        return problem(HttpStatus.NOT_FOUND, "User not found", exception.getMessage());
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
