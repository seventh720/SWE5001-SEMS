package com.sems.platform.catalog;
import jakarta.persistence.*;
import java.time.Instant;
import java.util.UUID;
@Entity @Table(name="events")
public class Event {
 @Id UUID id;
 @Column(name="organizer_id",nullable=false) UUID organizerId;
 @Column(nullable=false,length=200) String title;
 @Column(nullable=false,length=10000) String description;
 @Column(nullable=false,length=500) String location;
 @Column(name="starts_at",nullable=false) Instant startsAt;
 @Column(name="ends_at",nullable=false) Instant endsAt;
 @Column(nullable=false) int capacity;
 @Column(nullable=false,length=20) String status="DRAFT";
 @Version long version;
 @Column(name="created_at",nullable=false) Instant createdAt;
 @Column(name="updated_at",nullable=false) Instant updatedAt;
 protected Event(){}
 Event(UUID owner, Draft input){id=UUID.randomUUID();organizerId=owner;createdAt=Instant.now();apply(input);}
 void apply(Draft input){title=input.title().strip();description=input.description().strip();location=input.location().strip();startsAt=input.startsAt();endsAt=input.endsAt();capacity=input.capacity();updatedAt=Instant.now();}
 View view(){return new View(id,title,description,location,startsAt,endsAt,capacity,status,version,createdAt,updatedAt);}
 public record View(UUID id,String title,String description,String location,Instant startsAt,Instant endsAt,int capacity,String status,long version,Instant createdAt,Instant updatedAt){}
}
