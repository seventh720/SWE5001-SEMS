package com.sems.platform.identity.internal.application;
import java.util.Locale;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.web.server.ResponseStatusException;
public final class UsernamePolicy {
 private UsernamePolicy() {}
 public static String normalize(String value) {
  String name=value==null?"":value.strip().toLowerCase(Locale.ROOT);
  if(!name.matches("[a-z0-9._-]{3,50}") || !name.matches(".*[a-z0-9].*"))
   throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"Use 3–50 letters, numbers, dots, underscores or hyphens, including at least one letter or number.");
  if(Set.of("admin","administrator","support","system","root","sems").contains(name))
   throw new ResponseStatusException(HttpStatus.BAD_REQUEST,"This username is reserved. Choose another name.");
  return name;
 }
}
