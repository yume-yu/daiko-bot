let update_left = function(e){
  let times = e.target.value.split(":")
  let marginLeft = (((Number(times[0])-9) * 60) + Number(times[1])) / (10 * 60) * 100
  e.target.parentNode.parentNode.children[2].style.marginLeft =( (marginLeft < 0)  ? "0%"  : String(marginLeft)+"%")
  times = e.target.nextElementSibling.nextElementSibling.value.split(":")
  let marginRight = (100 - (((Number(times[0])-9) * 60) + Number(times[1])) / (10 * 60) * 100)
  e.target.parentNode.parentNode.children[2].style.marginRight = ( (marginRight > 100) ? "100%" : String(marginRight)+"%" )
}

let update_right = function(e){
  let times = e.target.value.split(":")
  let marginRight = (100 - (((Number(times[0])-9) * 60) + Number(times[1])) / (10 * 60) * 100)
  e.target.parentNode.parentNode.children[2].style.marginRight = ( (marginRight > 100) ? "100%" : String(marginRight)+"%" )
  times = e.target.previousElementSibling.previousElementSibling.value.split(":")
  let marginLeft = (((Number(times[0])-9) * 60) + Number(times[1])) / (10 * 60) * 100
  e.target.parentNode.parentNode.children[2].style.marginLeft =( (marginLeft < 0)  ? "0%"  : String(marginLeft)+"%")
}

let rm_row = function(e){
  console.log(e.target)
  if(e.target.parentNode.parentNode.parentNode.children.length > 2){
    e.target.parentNode.parentNode.parentNode.removeChild(e.target.parentNode.parentNode)
  }
}

let add_row = function(e){
  console.log(e.target)
  let row = (e.target.parentNode.parentNode.cloneNode(true));
  e.target.parentNode.parentNode.parentNode.insertBefore(row,e.target.parentNode.parentNode.nextSibling)
  let node = e.target.parentNode.parentNode.nextSibling
  console.log(node)
  node.children[0].children[6].addEventListener("click", add_row,false)
  node.children[0].children[7].addEventListener("click", rm_row,false)
  node.children[0].children[3].addEventListener("input", update_left,false)
  node.children[0].children[5].addEventListener("input", update_right,false)
  //update_eventlistener()
}

let update_eventlistener = function(){
  for(let node of document.getElementsByClassName("row")){
    node.children[0].children[6].addEventListener("click", add_row,false)
    node.children[0].children[7].addEventListener("click", rm_row,false)
    node.children[0].children[3].addEventListener("input", update_left,false)
    node.children[0].children[5].addEventListener("input", update_right,false)
  }
}

let days = document.getElementsByClassName("weekday")
for(let day of days){
  let origin = document.getElementById("origin").cloneNode(true)
  origin.removeAttribute("id")
  origin.setAttribute("class","row")
  day.append(origin)
}

update_eventlistener()

let get_data = function(){
  const shift = {};
  let range = document.getElementById("date_range").getElementsByTagName("input")
  shift["begin"] = range["start-day"].value
  shift["finish"] = range["end-day"].value

  let days = document.getElementsByClassName("weekday")
  for(let day of days){
    let weekday =day.getAttribute("id") ;
    shift[weekday] = []
    let works = day.getElementsByClassName("row")
    for(let work of works){
      console.log(work.getElementsByTagName("span")[0].children[1])
      let target = work.getElementsByTagName("span")[0].children
      shift[weekday].push({"name":target[1].selectedOptions[0].label,"slackid":target[1].value, "start":target[3].value, "end":target[5].value})
    }
  }
  console.log(JSON.stringify(shift))
  return JSON.stringify(shift)
}

let send_data = function(url, data){
  console.log(url);
  let xhr = new XMLHttpRequest();
  xhr.open("POST", url);
  xhr.setRequestHeader("Content-Type", "application/json");
  xhr.onload = () => {
    console.log(xhr.status);
    console.log("success!");
  };
  xhr.onerror = () => {
    console.log(xhr.status);
    console.log("error!");
  };
  xhr.send(data);
}
