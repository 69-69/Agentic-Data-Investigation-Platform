package com.portfolio.investigation.api;

import java.net.URI;
import java.util.UUID;
import jakarta.validation.Valid;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import com.portfolio.investigation.application.InvestigationService;
import com.portfolio.investigation.domain.Investigation.Status;

@RestController
@RequestMapping("/api/v1/investigations")
public class InvestigationController {
    private final InvestigationService service;
    public InvestigationController(InvestigationService service) { this.service = service; }
    @PostMapping
    public ResponseEntity<ApiDtos.Created> create(@Valid @RequestBody ApiDtos.CreateRequest request,
            @RequestAttribute(CorrelationFilter.HEADER) String correlationId) {
        var result = service.create(request.question(), correlationId);
        int status = result.status() == Status.PENDING || result.status() == Status.RUNNING ? 202 : 201;
        return ResponseEntity.status(status).location(URI.create("/api/v1/investigations/" + result.id()))
            .body(ApiDtos.created(result));
    }
    @GetMapping("/{id}")
    public ApiDtos.Result get(@PathVariable UUID id, @RequestAttribute(CorrelationFilter.HEADER) String correlationId) {
        return ApiDtos.result(service.get(id, correlationId));
    }
}
