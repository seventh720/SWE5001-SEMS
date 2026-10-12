package com.sems.platform.catalog;
import java.util.*;
import org.springframework.data.domain.*;
import org.springframework.data.jpa.repository.JpaRepository;
public interface EventRepository extends JpaRepository<Event,UUID>{
 Optional<Event> findByIdAndOrganizerId(UUID id,UUID owner);
 Page<Event> findByOrganizerId(UUID owner,Pageable page);
}
