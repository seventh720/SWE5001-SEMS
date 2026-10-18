package com.sems.platform.catalog;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.data.jpa.repository.JpaRepository;
public interface EventRepository extends JpaRepository<Event,UUID>{
 Page<Event> findByOrganizationId(UUID organizationId,Pageable page);
 @org.springframework.data.jpa.repository.Lock(jakarta.persistence.LockModeType.PESSIMISTIC_WRITE)
 @org.springframework.data.jpa.repository.Query("select e from Event e where e.id=:id")
 Optional<Event> lockById(@org.springframework.data.repository.query.Param("id") UUID id);
 @org.springframework.data.jpa.repository.Query("select e from Event e where e.organizationId in :activeOrgs and e.status='PUBLISHED' and e.startsAt>:now and lower(e.title) like lower(concat('%',:keyword,'%')) and (:category is null or e.category=:category) and ((:org is null and e.visibility='PUBLIC') or (:org is not null and e.organizationId=:org))")
 Page<Event> discover(@org.springframework.data.repository.query.Param("activeOrgs") List<UUID> activeOrgs,@org.springframework.data.repository.query.Param("org") UUID org,@org.springframework.data.repository.query.Param("now") java.time.Instant now,@org.springframework.data.repository.query.Param("keyword") String keyword,@org.springframework.data.repository.query.Param("category") EventCategory category,Pageable page);
 @org.springframework.data.jpa.repository.Query("select distinct e.organizationId from Event e where e.status='PUBLISHED' and e.startsAt>:now and lower(e.title) like lower(concat('%',:keyword,'%')) and (:category is null or e.category=:category) and ((:org is null and e.visibility='PUBLIC') or (:org is not null and e.organizationId=:org)) order by e.organizationId")
 org.springframework.data.domain.Slice<UUID> discoveryOrganizations(@org.springframework.data.repository.query.Param("org") UUID org,@org.springframework.data.repository.query.Param("now") java.time.Instant now,@org.springframework.data.repository.query.Param("keyword") String keyword,@org.springframework.data.repository.query.Param("category") EventCategory category,Pageable page);
 List<Event> findTop20ByStatusOrderByUpdatedAtAsc(String status);
}
