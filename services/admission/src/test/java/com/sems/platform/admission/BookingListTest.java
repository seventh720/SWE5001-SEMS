package com.sems.platform.admission;

import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.List;
import java.util.UUID;
import org.junit.jupiter.api.Test;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.jdbc.core.RowMapper;
import org.springframework.web.server.ResponseStatusException;
import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.*;
import static org.mockito.Mockito.*;

class BookingListTest {
    @Test void statusPaginationUsesTheOwnersFilteredTotal() {
        var jdbc=mock(JdbcTemplate.class);
        var user=UUID.randomUUID();
        var service=new BookingService(jdbc,new ObjectMapper());
        for (String status : List.of("CONFIRMED","CANCELLED")) {
            when(jdbc.queryForObject(anyString(),eq(Long.class),eq(user),eq(status))).thenReturn(12L);
            when(jdbc.query(anyString(),any(RowMapper.class),eq(user),eq(status),eq(10),eq(10L))).thenReturn(List.of());
            var result=service.list(user,1,10,status);
            assertEquals(12,result.totalElements());
            assertEquals(2,result.totalPages());
            verify(jdbc).queryForObject("SELECT count(*) FROM bookings WHERE user_id=? AND status=?",Long.class,user,status);
            verify(jdbc).query(eq("SELECT * FROM bookings WHERE user_id=? AND status=? ORDER BY created_at DESC,id DESC LIMIT ? OFFSET ?"),any(RowMapper.class),eq(user),eq(status),eq(10),eq(10L));
        }
    }
    @Test void invalidStatusIsRejectedBeforeQuerying() {
        var jdbc=mock(JdbcTemplate.class);
        var service=new BookingService(jdbc,new ObjectMapper());
        var error=assertThrows(ResponseStatusException.class,()->service.list(UUID.randomUUID(),0,10,"UNKNOWN"));
        assertEquals(400,error.getStatusCode().value());
        verifyNoInteractions(jdbc);
    }
    @Test void omittedStatusKeepsExistingApiCompatible() {
        var jdbc=mock(JdbcTemplate.class);
        var user=UUID.randomUUID();
        when(jdbc.queryForObject(anyString(),eq(Long.class),eq(user))).thenReturn(0L);
        when(jdbc.query(anyString(),any(RowMapper.class),eq(user),eq(10),eq(0L))).thenReturn(List.of());
        var result=new BookingService(jdbc,new ObjectMapper()).list(user,0,10,null);
        assertEquals(0,result.totalElements());
        verify(jdbc).queryForObject("SELECT count(*) FROM bookings WHERE user_id=?",Long.class,user);
    }
}
