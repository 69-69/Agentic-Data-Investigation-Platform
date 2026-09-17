package com.portfolio.investigation.api;

import jakarta.servlet.http.HttpServletRequest;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.ErrorResponse;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import com.portfolio.investigation.application.ServiceFailure;

@RestControllerAdvice
public class ApiExceptionHandler {
    private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);
    @ExceptionHandler(ServiceFailure.class)
    public ResponseEntity<ApiDtos.ErrorResponse> downstream(ServiceFailure error, HttpServletRequest request) {
        return switch (error.kind()) {
            case NOT_FOUND -> response(404, "INVESTIGATION_NOT_FOUND", "Investigation not found.", request);
            case UNAVAILABLE -> response(503, "AGENT_UNAVAILABLE", "The investigation service is unavailable.", request);
            case TIMEOUT -> response(504, "AGENT_TIMEOUT", "The investigation service timed out.", request);
            case BAD_RESPONSE -> response(502, "AGENT_BAD_RESPONSE", "The investigation service returned an invalid response.", request);
        };
    }
    @ExceptionHandler(Exception.class)
    public ResponseEntity<ApiDtos.ErrorResponse> unexpected(Exception error, HttpServletRequest request) {
        if (error instanceof ErrorResponse framework) {
            int status = framework.getStatusCode().value();
            if (status >= 400 && status < 500)
                return response(status, status == 400 ? "INVALID_REQUEST" : "HTTP_"+status,
                    "The request could not be processed.", request);
        }
        if (error instanceof org.springframework.http.converter.HttpMessageNotReadableException
            || error instanceof org.springframework.web.method.annotation.MethodArgumentTypeMismatchException)
            return response(400, "INVALID_REQUEST", "Provide a valid request with a question of 1–2000 characters.", request);
        log.atError().addKeyValue("event", "unexpected_error").log("Request failed unexpectedly");
        return response(500, "INTERNAL_ERROR", "The request could not be completed.", request);
    }
    private ResponseEntity<ApiDtos.ErrorResponse> response(int status, String code, String message, HttpServletRequest request) {
        String id = (String) request.getAttribute(CorrelationFilter.HEADER);
        return ResponseEntity.status(status).body(new ApiDtos.ErrorResponse(new ApiDtos.ErrorDetail(code, message), id));
    }
}
