package com.sems.platform.catalog;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.data.jpa.repository.JpaRepository;
public interface EventRepository extends JpaRepository<Event,UUID>{
 Optional<Event> findByIdAndOrganizerId(UUID id,UUID owner);
 Page<Event> findByOrganizationId(UUID organizationId,Pageable page);
 Page<Event> findByOrganizerId(UUID owner,Pageable page);
 @org.springframework.data.jpa.repository.Lock(jakarta.persistence.LockModeType.PESSIMISTIC_WRITE)
 @org.springframework.data.jpa.repository.Query("select e from Event e where e.id=:id")
 Optional<Event> lockById(@org.springframework.data.repository.query.Param("id") UUID id);
 @org.springframework.data.jpa.repository.Query("select e from Event e where e.status='PUBLISHED' and e.startsAt>:now and lower(e.title) like lower(concat('%',:keyword,'%')) and (:category is null or e.category=:category) and ((:org is null and e.visibility='PUBLIC') or (:org is not null and e.organizationId=:org))")
 Page<Event> discover(@org.springframework.data.repository.query.Param("org") UUID org,@org.springframework.data.repository.query.Param("now") java.time.Instant now,@org.springframework.data.repository.query.Param("keyword") String keyword,@org.springframework.data.repository.query.Param("category") EventCategory category,Pageable page);
 List<Event> findTop20ByStatusOrderByUpdatedAtAsc(String status);
 Page<Event> findByStatusAndStartsAtAfterAndTitleContainingIgnoreCase(String status,java.time.Instant now,String keyword,Pageable page);
 Page<Event> findByStatusAndCategoryAndStartsAtAfterAndTitleContainingIgnoreCase(String status,EventCategory category,java.time.Instant now,String keyword,Pageable page);
}
