package com.sems.platform.identity.internal.persistence;

import com.sems.platform.identity.internal.domain.UserAccount;
import java.util.Optional;
import java.util.UUID;
import org.springframework.data.jpa.repository.JpaRepository;

public interface UserAccountRepository extends JpaRepository<UserAccount, UUID> {

    @org.springframework.data.jpa.repository.Query("select u from UserAccount u where locate(lower(:search),lower(u.username))>0 or locate(lower(:search),lower(u.email))>0")
    org.springframework.data.domain.Page<UserAccount> search(@org.springframework.data.repository.query.Param("search") String search, org.springframework.data.domain.Pageable page);

    Optional<UserAccount> findByEmail(String email);

    boolean existsByEmail(String email);

    boolean existsByUsername(String username);
}
