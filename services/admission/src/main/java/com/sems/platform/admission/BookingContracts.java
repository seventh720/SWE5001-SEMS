package com.sems.platform.admission;
import jakarta.validation.constraints.*;
import java.time.Instant;
import java.util.*;
public class BookingContracts {
    public record Request(@NotNull UUID requestKey, @NotNull UUID eventId, @NotNull UUID ticketTypeId,
                          @Min(1) @Max(10) int quantity, @jakarta.validation.Valid AttendeeInfo attendeeInfo) {
        public Request {attendeeInfo=attendeeInfo==null?AttendeeInfo.empty():attendeeInfo;}
    }
    public record Ticket(UUID id, String credential, String state) {}
    public record Booking(UUID id, UUID eventId, UUID ticketTypeId, int quantity, String status,
                          String eventTitle, String eventLocation, Instant startsAt, Instant endsAt,
                          String ticketName, int amount, Instant createdAt, List<Ticket> tickets, AttendeeInfo attendeeInfo, String customFieldLabel, String eventCancellationReason, CatalogClient.EventDetails currentEvent) {
        public Booking withCurrentEvent(CatalogClient.EventDetails event) {
            return new Booking(id,eventId,ticketTypeId,quantity,status,eventTitle,eventLocation,startsAt,endsAt,ticketName,amount,createdAt,tickets,attendeeInfo,customFieldLabel,eventCancellationReason,event);
        }
    }
    public record OrganizerBooking(UUID id, String status, String ticketName, int quantity, Instant createdAt,
        AttendeeInfo attendeeInfo, String customFieldLabel) {}
    public record OrganizerPage(List<OrganizerBooking> items, int page, int size, long totalElements, long totalPages) {}
    public record Page(List<Booking> items, int page, int size, long totalElements, long totalPages) {}
}
