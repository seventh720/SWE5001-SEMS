package com.sems.platform.catalog;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.data.jpa.repository.JpaRepository;
public interface EventRepository extends JpaRepository<Event,UUID>{
 Optional<Event> findByIdAndOrganizerId(UUID id,UUID owner);
 Page<Event> findByOrganizerId(UUID owner,Pageable page);
 @org.springframework.data.jpa.repository.Lock(jakarta.persistence.LockModeType.PESSIMISTIC_WRITE)
 @org.springframework.data.jpa.repository.Query("select e from Event e where e.id=:id")
 Optional<Event> lockById(@org.springframework.data.repository.query.Param("id") UUID id);
 List<Event> findTop20ByStatusOrderByUpdatedAtAsc(String status);
 Page<Event> findByStatusAndStartsAtAfterAndTitleContainingIgnoreCase(String status,java.time.Instant now,String keyword,Pageable page);
}
